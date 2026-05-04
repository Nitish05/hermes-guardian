from hermes_guardian.recognition import _sample_status, enrollment_prompts


def test_enrollment_prompts_repeat_to_requested_sample_count():
    prompts = enrollment_prompts(9)

    assert len(prompts) == 9
    assert prompts[0] == "Look straight at the camera"
    assert prompts[7] == "Look straight at the camera"


def test_sample_status_guides_valid_single_face_frames():
    assert _sample_status(0) == "no face found"
    assert _sample_status(1) == "hold still"
    assert _sample_status(2) == "multiple faces found"
