import unittest

from songssx_workflow import validate_dimensions, validate_shots


def prompt(description):
    return (
        'subject_definitions: <Picture 1> sets the room.\n'
        'summary: A pause.\nretention_analysis: Keep the room.\n'
        f'detailed_description: {description}\n'
        'overall_soundscape: Room tone.\nnon_diegetic_music: N/A'
    )


class ShotChecks(unittest.TestCase):
    def test_requires_contiguous_shots_starting_with_shot_one(self):
        for description in ('Hold.', '[Shot 2] At 00:01.000, cut.',
                            '[Shot 1] Hold. [Shot 3] At 00:01.000, cut.',
                            '[Shot 1] Hold. [Shot 1] Hold.'):
            with self.subTest(description=description), self.assertRaisesRegex(ValueError, '连续镜号'):
                validate_shots(prompt(description), 2, 124, 22)

    def test_accepts_continuous_shot_and_cuts_at_rounded_overlap_boundary(self):
        validate_shots(prompt('[Shot 1] The same shot continues.'), 2, 124, 22)
        for overlap, timestamp in ((22, '00:00.917'), (5, '00:00.208')):
            with self.subTest(overlap=overlap):
                validate_shots(prompt(f'[Shot 1] Hold. [Shot 2] At {timestamp}, cut.'), 2, 124, overlap)

    def test_rejects_early_missing_repeated_and_out_of_range_cut_times(self):
        for next_shots, error in (
            ('[Shot 2] At 00:00.400, cut.', '重叠区内'),
            ('[Shot 2] Cut to a new angle.', '标出切镜时码'),
            ('[Shot 2] At 00:01.000, cut. [Shot 3] At 00:01.000, cut.', '严格递增'),
            ('[Shot 2] At 00:06.000, cut.', '采样区间内'),
        ):
            with self.subTest(next_shots=next_shots), self.assertRaisesRegex(ValueError, error):
                validate_shots(prompt(f'[Shot 1] Hold. {next_shots}'), 2, 124, 22)

    def test_checks_both_dimension_limits_and_alignment(self):
        validate_dimensions(32, 16384)
        for width, height in ((0, 736), (1280, 16416), (16416, 736), (1280, 735)):
            with self.subTest(width=width, height=height), self.assertRaisesRegex(ValueError, '对齐 32'):
                validate_dimensions(width, height)
