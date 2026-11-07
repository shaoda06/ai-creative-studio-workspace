"""Review provenance and direct suggestion references in temporary workspaces."""
from pathlib import Path
import tempfile
import unittest

from chloe_init import initialize_workspace, initialize_video
import chloe_documents as docs


class ChloeReviewTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = initialize_workspace(Path(temp.name)/'Chloe Workspace')
        self.video = initialize_video(self.root, 'V001', '展示')
        self.readme = self.video/'README.md'
        self.review = self.root/'综合资料/运营复盘.md'
        self.time = '2026-11-08T10:00:00+08:00'
        (self.video/'成片/test.mp4').write_bytes(b'path-only fixture')
        (self.video/'执行记录/证据.md').write_text('隔离原始核对记录')
        self.source = f'[R001](<../projects/{self.video.name}/README.md#单条复盘>)'

    def append(self, path, section, row):
        text = path.read_text()
        start = text.index('## '+section+'\n')
        end = text.index('\n\n', text.index('| ---', start))
        path.write_text(text[:end]+'\n| '+' | '.join(row)+' |'+text[end:])

    def read(self, path):
        entry = next(e for e in docs.documents(self.root) if e[0] == path)
        return docs.read_document(self.root, *entry)

    def content_review(self):
        self.append(self.readme, '单条复盘', ['R001', '不适用', '[原成片](<成片/test.mp4>)开场构图',
                    '不适用', '仅分析内容', '调整开场'])

    def metrics(self):
        self.readme.write_text(self.readme.read_text().replace('| 视频状态 | 制作中 |', '| 视频状态 | 已发布 |'))
        self.append(self.readme, '发布记录', ['P001', '[成片](<成片/test.mp4>)', '不适用', '文案',
                    '不适用', '不适用', '不适用', '不适用', self.time, '立即发布', '已发布',
                    'post-id', 'https://example.com/post', '用户确认', '[发布结果](<执行记录/证据.md>)'])
        self.append(self.readme, '效果数据', ['D001', 'P001', self.time, self.time, self.time,
                    '播放量', '10', '次', '平台原值', '[原始数据](<执行记录/证据.md>)'])

    def test_single_review_can_be_verified_without_cross_video_copy(self):
        self.content_review()
        baseline = self.review.read_text()
        row = ['T001', self.source, '待决定', '未取得', '未取得', '未取得', '未取得', '未取得']
        self.append(self.review, '建议验证', row)
        parsed = self.read(self.review)
        self.assertEqual(docs.records(parsed, '跨视频结论'), [])
        self.assertEqual(docs.records(parsed, '建议验证')[0]['复盘编号'], self.source)
        for source in ('R001', self.source.replace('R001', 'R999'), self.source.replace('R001', 'D001'),
                       self.source.replace('#单条复盘', '#效果数据'),
                       '[R001](<运营复盘.md#跨视频结论>)', '[R001](<https://example.com/review>)'):
            with self.subTest(source=source):
                self.review.write_text(baseline)
                bad = row.copy(); bad[1] = source
                self.append(self.review, '建议验证', bad)
                with self.assertRaises(ValueError): self.read(self.review)
        self.review.write_text(baseline)
        self.append(self.review, '跨视频结论', ['R001', self.time, self.time, self.time,
                    self.source, '同类内容', '待验证假设', '样本不足', '调整开场'])
        row[1] = 'R001'
        self.append(self.review, '建议验证', row)
        self.read(self.review)
        other = initialize_video(self.root, 'V002', '对照')
        self.review.write_text(baseline)
        row[1] = self.source.replace(self.video.name, other.name)
        self.append(self.review, '建议验证', row)
        with self.assertRaisesRegex(ValueError, '不存在的复盘编号'): self.read(self.review)

    def test_cross_video_sources_resolve_record_ids_and_original_evidence(self):
        self.metrics(); self.content_review()
        baseline = self.review.read_text()
        capture = self.source.replace('R001', 'D001').replace('#单条复盘', '#效果数据')
        for source in (self.source, capture, self.source+'、'+capture):
            self.review.write_text(baseline)
            self.append(self.review, '跨视频结论', ['R001', self.time, self.time, self.time,
                        source, '同口径', '待验证假设', '样本不足', '调整开场'])
            self.read(self.review)
        valid = self.review.read_text()
        for source in ('未取得', 'V001 D001', capture.replace('D001', 'D999'),
                       capture.replace('D001', 'V001 D999'), self.source.replace('R001', 'R999'),
                       capture.replace('README.md', '脚本.md'), capture.replace('#效果数据', '#单条复盘')):
            with self.subTest(source=source):
                self.review.write_text(baseline)
                self.append(self.review, '跨视频结论', ['R001', self.time, self.time, self.time,
                            source, '同口径', '结论', '局限', '建议'])
                with self.assertRaises(ValueError): self.read(self.review)
        self.review.write_text(valid)
        original = self.readme.read_text()
        for before, after, error in (
            ('[原始数据](<执行记录/证据.md>)', '后台截图', '实际指标须链接'),
            ('| 播放量 | 10 |', '| 播放量 | 未取得 |', '尚无实际指标值'),
            ('[原成片](<成片/test.mp4>)开场构图', '开场构图', '纯内容复盘须'),
        ):
            self.readme.write_text(original.replace(before, after))
            with self.assertRaisesRegex(ValueError, error): self.read(self.review)

    def test_metrics_require_published_fact_and_traceable_sources(self):
        self.metrics()
        original = self.readme.read_text()
        self.read(self.readme)
        for status in ('待提交', '已提交', '审核中', '失败', '待核实'):
            with self.subTest(status=status):
                self.readme.write_text(original.replace('| 视频状态 | 已发布 |', '| 视频状态 | 待发布 |')
                                       .replace('| 立即发布 | 已发布 |', '| 立即发布 | '+status+' |'))
                with self.assertRaisesRegex(ValueError, '实际发布依据'): self.read(self.readme)
        withdrawn = original.replace('| 视频状态 | 已发布 |', '| 视频状态 | 待发布 |').replace('| 立即发布 | 已发布 |', '| 立即发布 | 已撤回 |')
        self.readme.write_text(withdrawn)
        self.read(self.readme)
        self.readme.write_text(withdrawn.replace('| '+self.time+' | 立即发布', '| 未取得 | 立即发布'))
        with self.assertRaisesRegex(ValueError, '实际发布依据'): self.read(self.readme)
        for before, after, error in (
            ('[发布结果](<执行记录/证据.md>)', '已看过', '发布结果证据'),
            ('[原始数据](<执行记录/证据.md>)', '未取得', '实际指标须链接'),
            ('[原始数据](<执行记录/证据.md>)', '后台截图', '实际指标须链接'),
            ('[原始数据](<执行记录/证据.md>)', '[目录](<执行记录/>)', '实际指标须链接'),
            ('[原始数据](<执行记录/证据.md>)', '[丢失](<执行记录/不存在.md>)', '文件链接不存在'),
            ('| D001 | P001 | '+self.time, '| D001 | P001 | 2026-11-08T01:59:59+00:00', '早于实际发布时间'),
            ('| D001 | P001 |', '| D001 | P999 |', '不存在的发布编号'),
        ):
            self.readme.write_text(original.replace(before, after))
            with self.assertRaisesRegex(ValueError, error): self.read(self.readme)
        for source in ('https://example.com/metrics', '[来源](<https://example.com/metrics>)'):
            self.readme.write_text(original.replace('[原始数据](<执行记录/证据.md>)', source))
            self.read(self.readme)
        # Missing metrics are not fabricated, and calendar-day windows can begin before publication.
        self.readme.write_text(original.replace('| 播放量 | 10 |', '| 播放量 | 未取得 |')
                               .replace('[原始数据](<执行记录/证据.md>)', '未取得')
                               .replace('| D001 | P001 | '+self.time+' | '+self.time,
                                        '| D001 | P001 | '+self.time+' | 2026-11-08T00:00:00+08:00'))
        self.read(self.readme)

    def test_content_review_requires_original_file_or_analysis_link(self):
        self.content_review()
        original = self.readme.read_text()
        for value in ('看过成片', '[目录](<成片/>)', '[丢失](<成片/missing.mp4>)'):
            self.readme.write_text(original.replace('[原成片](<成片/test.mp4>)', value))
            with self.assertRaises(ValueError): self.read(self.readme)
        self.readme.write_text(original.replace('[原成片](<成片/test.mp4>)', '[分析记录](<执行记录/证据.md>)'))
        self.read(self.readme)

    def test_data_review_cannot_use_an_empty_capture_as_evidence(self):
        self.metrics()
        self.append(self.readme, '单条复盘', ['R001', 'D001', '内容观察', '仅说明数据变化', '样本有限', '调整开场'])
        self.read(self.readme)
        self.readme.write_text(self.readme.read_text().replace('| 播放量 | 10 |', '| 播放量 | 未取得 |'))
        with self.assertRaisesRegex(ValueError, '单条复盘引用的采集记录尚无实际指标值'):
            self.read(self.readme)


if __name__ == '__main__':
    unittest.main()
