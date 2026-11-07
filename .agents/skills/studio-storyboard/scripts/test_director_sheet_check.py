import copy
import json
from pathlib import Path
import tempfile
import unittest
from director_sheet_check import check_plan, COLUMNS
from storyboard_fields import FIELDS


class DirectorSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'plan.json'
        self.rows = []
        text = ''
        for n in range(1, 8):
            identity = f'SH{n:03}'
            fields = {field: '无' for field in FIELDS}
            fields.update({'镜号': identity, '台词': '甲：好。\n乙（画外）：走吧。', '时长': '3.5秒', '景别': '中景', '运镜': '固定'})
            text += '\n### ' + identity + '｜镜头\n\n' + '\n\n'.join('**'+k+'**：'+v for k,v in fields.items())+'\n'
            self.rows.append({key: '结构草图' if key=='分镜图' else fields[key] for key in COLUMNS})
        (self.root/'source.md').write_text(text)
        self.plan = {'source':'source.md','source_version':'v03','chart_version':'v01','object':'独立对象','candidate':1,'extra_fields':[],
                     'shot_ids':[r['镜号'] for r in self.rows], 'pages':[{'page':1,'rows':self.rows[:6]}, {'page':2,'rows':self.rows[6:]}]}

    def run_plan(self, plan):
        self.path.write_text(json.dumps(plan,ensure_ascii=False))
        return check_plan(self.path)

    def test_complete_multiline_and_independent_versions(self):
        result=self.run_plan(self.plan)
        self.assertEqual((result['pages'],result['shots'],result['source_version'],result['chart_version']),(2,7,'v03','v01'))

    def test_business_extra_fields_are_explicit(self):
        source=self.root/'source.md'
        text=source.read_text()
        parts=text.split('\n### ')[1:]
        source.write_text(''.join('\n### '+part.rstrip()+'\n\n**业务补充**：无\n' for part in parts))
        with self.assertRaisesRegex(ValueError,'未声明字段'):self.run_plan(self.plan)
        self.plan['extra_fields']=['业务补充']
        self.assertEqual(self.run_plan(self.plan)['shots'],7)

    def test_partial_scope_keeps_source_order(self):
        self.plan['shot_ids']=['SH002','SH003'];self.plan['pages']=[{'page':1,'rows':self.rows[1:3]}]
        self.assertEqual(self.run_plan(self.plan)['shots'],2)

    def test_reject_lost_dialogue_line_and_changed_duration(self):
        for key,value in [('台词','甲：好。'),('时长','3秒'),('音效','脚步声')]:
            with self.subTest(key=key):
                plan=copy.deepcopy(self.plan);plan['pages'][0]['rows'][0][key]=value
                with self.assertRaisesRegex(ValueError,'完整原文'):self.run_plan(plan)

    def test_reject_missing_duplicate_reordered_shots(self):
        for rows in [self.rows[:5], self.rows[:5]+[self.rows[0]], list(reversed(self.rows[:6]))]:
            with self.subTest(rows=rows):
                plan=copy.deepcopy(self.plan);plan['pages'][0]['rows']=rows
                with self.assertRaisesRegex(ValueError,'分页镜头'):self.run_plan(plan)

    def test_reject_seven_rows_or_wrong_page(self):
        for pages in [[{'page':1,'rows':self.rows}],[{'page':2,'rows':self.rows[:6]}]]:
            plan=copy.deepcopy(self.plan);plan['pages']=pages
            with self.assertRaisesRegex(ValueError,'页码'):self.run_plan(plan)

    def test_reject_column_and_unknown_scope(self):
        plan=copy.deepcopy(self.plan);del plan['pages'][0]['rows'][0]['音效']
        with self.assertRaisesRegex(ValueError,'八列'):self.run_plan(plan)
        plan=copy.deepcopy(self.plan);plan['shot_ids']=['SH999']
        with self.assertRaisesRegex(ValueError,'制作范围'):self.run_plan(plan)


if __name__=='__main__':unittest.main()
