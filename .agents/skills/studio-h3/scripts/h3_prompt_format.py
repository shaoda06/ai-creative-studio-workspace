"""H3 input-mode, section and keyframe syntax; no business identities or review policy."""
import hashlib
import re

SECTIONS = ('subject_definitions', 'summary', 'retention_analysis', 'detailed_description', 'overall_soundscape', 'non_diegetic_music')
BASE_SECTIONS = ('integrated_multimodal_description', 'overall_soundscape', 'non_diegetic_music')
REFERENCE_MODES = ('r2v', 'v2v', 'rv2v')
PROMPT_CHARACTER_LIMIT = 7000

def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def sections(text, headings=SECTIONS, allow_prefix=False):
    matches = list(re.finditer(r'^(' + '|'.join(headings) + r'):[ \t]*', text, re.M))
    if [m[1] for m in matches] != list(headings) or (not allow_prefix and text[:matches[0].start()].strip()):
        return None
    return {m[1]: text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()
            for i, m in enumerate(matches)}


def shot_blocks(prompt, mode='r2v'):
    parsed = sections(prompt, SECTIONS if mode in REFERENCE_MODES else BASE_SECTIONS,
                      allow_prefix=mode not in REFERENCE_MODES)
    body = parsed['detailed_description' if mode in REFERENCE_MODES else 'integrated_multimodal_description']
    return [(int(m[1]), m[2].strip()) for m in re.finditer(
        r'\[Shot (\d+)\](.*?)(?=\[Shot \d+\]|\Z)', body, re.S)]


def format_findings(prompt, *, mode='r2v', images=None, duration=None):
    errors = []
    def issue(code, detail):
        errors.append({'code': code, 'detail': detail})
    reference = mode in REFERENCE_MODES
    headings = SECTIONS if reference else BASE_SECTIONS
    english = sections(prompt, headings, allow_prefix=not reference)
    if english is None:
        issue('sections', '英文必须包含完整且有序的' + ('Ref2VA六节' if reference else '基础模式三节'))
        return errors
    prefix = prompt[:prompt.index(headings[0] + ':')].strip()
    if not reference:
        slots = images if images is not None else ({0, 1} if mode == 'fl2v' else {0} if mode == 'i2v' else set())
        if mode == 'fl2v':
            if slots == {0, 1}:
                valid = prefix.startswith('How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 ')
            elif slots == {0}:
                valid = prefix == 'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.'
            elif slots == {1}:
                valid = prefix.startswith('How the reference pictures align with the target video — <Picture 1> ')
            else:
                valid = not slots and not prefix
        elif mode == 'i2v':
            valid = slots == {0} and prefix == 'For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.'
        else:
            valid = mode == 't2v' and not prefix and not slots
        if not valid:
            issue('keyframe_alignment', '模式、首尾图槽位与首行对齐指令不对应')
        if mode == 'fl2v' and 1 in slots:
            ending = re.search(r'\(from (?:\[)?Shot (\d+)(?:\])?\) aligns with the (\d+\.\d{2})-second mark of the target video\.$', prefix)
            if not ending or int(ending[1]) != len(re.findall(r'\[Shot \d+\]', english[headings[0]])) or (duration is not None and abs(float(ending[2]) - duration) > .011):
                issue('keyframe_timing', '尾帧对齐时间或最后镜号与本段不一致')
    return errors
