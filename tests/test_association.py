from focusguard.association import associate_faces, associate_phones, containment, iou

PERSONS = {1: (0, 0, 100, 300), 2: (120, 0, 220, 300)}


def test_iou_and_containment():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert containment((0, 0, 10, 10), (0, 0, 100, 100)) == 1.0
    assert containment((95, 0, 105, 10), (0, 0, 100, 100)) == 0.5


def test_phone_inside_person_is_associated():
    out = associate_phones(PERSONS, [((30, 150, 60, 200), 0.8)], min_confidence=0.35, min_containment=0.6)
    assert out == {1: 0.8}


def test_low_confidence_phone_is_ignored():
    assert associate_phones(PERSONS, [((30, 150, 60, 200), 0.2)], 0.35, 0.6) == {}


def test_corner_overlap_is_not_enough():
    # phone mostly outside the person box (only a corner overlaps)
    out = associate_phones(PERSONS, [((90, 150, 118, 200), 0.9)], 0.35, 0.6)
    assert out == {}


def test_phone_assigned_to_one_person_only():
    persons = {1: (0, 0, 200, 300), 2: (100, 0, 300, 300)}   # overlapping people
    out = associate_phones(persons, [((110, 150, 140, 200), 0.9)], 0.35, 0.6)
    assert len(out) == 1


def test_faces_associated_one_to_one_in_head_region():
    faces = [(30, 10, 70, 60), (150, 10, 190, 60), (40, 250, 60, 280)]   # last face is at waist height
    out = associate_faces(PERSONS, faces)
    assert out == {1: 0, 2: 1}


def test_laptop_close_up_face_is_associated():
    """Regression (real webcam run): a close-up person box is mostly head and
    shoulders, so the face centre sits near the middle of the box."""
    persons = {1: (300, 80, 980, 720)}          # head+shoulders filling a 1280x720 frame
    face = (480, 240, 800, 640)                  # centre y = 440 -> 0.56 of the box height
    assert associate_faces(persons, [face]) == {1: 0}


def test_face_of_student_behind_goes_to_that_student():
    front = (200, 200, 700, 720)
    back = (420, 60, 620, 500)
    faces = [(460, 90, 560, 190),                # back student's face (inside front box too? no: above it)
             (380, 260, 520, 400)]               # front student's face
    out = associate_faces({1: front, 2: back}, faces)
    assert out == {2: 0, 1: 1}
