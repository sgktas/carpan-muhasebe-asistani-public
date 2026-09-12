from app.core.review_queue import ReviewMember, ReviewQueue, ReviewQueueError


def member(row=1, amount=125.5):
    return ReviewMember("banka.xlsx", row, amount, "ANTALYA", "GARANTI", "tutar farkı")


def test_review_group_survives_reopen_and_keeps_all_members(tmp_path):
    database = tmp_path / "operations.sqlite3"
    first = ReviewQueue(database, company_id=7)
    group_id = first.enqueue([member(4), member(5, 50)], operation_id=91)

    reopened = ReviewQueue(database, company_id=7)
    groups = reopened.list()
    assert len(groups) == 1
    assert groups[0].group_id == group_id
    assert [item.source_row for item in groups[0].members] == [4, 5]
    assert groups[0].total_amount == 175.5


def test_review_assignment_resolution_and_reopen_are_state_checked(tmp_path):
    queue = ReviewQueue(tmp_path / "operations.sqlite3", company_id=1)
    group_id = queue.enqueue([member()])
    queue.assign(group_id, user_id=9)
    queue.resolve(group_id, user_id=9, resolution_code="HAVALE")
    assert queue.list(status="OPEN") == []
    assert queue.list(status="RESOLVED")[0].status == "RESOLVED"
    queue.reopen(group_id, user_id=9)
    assert queue.list()[0].status == "OPEN"

    try:
        queue.resolve(group_id, user_id=9, resolution_code="")
    except ValueError:
        pass
    else:
        raise AssertionError("boş sonuç kodu kabul edilmemeli")


def test_review_queue_is_company_scoped(tmp_path):
    database = tmp_path / "operations.sqlite3"
    ReviewQueue(database, company_id=1).enqueue([member()])
    other = ReviewQueue(database, company_id=2)
    assert other.list() == []
    try:
        other.assign("missing", user_id=1)
    except ReviewQueueError:
        pass
    else:
        raise AssertionError("firma dışı kayıt değiştirilememeli")


def test_review_members_keep_content_hash_sheet_and_source_integrity(tmp_path):
    source = tmp_path / "banka.xlsx"
    source.write_bytes(b"ilk kaynak")
    queue = ReviewQueue(tmp_path / "operations.sqlite3", company_id=1)
    group_id = queue.enqueue([
        ReviewMember("banka.xlsx", 4, 125.5, "ANTALYA", "GARANTI", "tutar farkı",
                     queue.file_hash(source), "Hareketler"),
    ])
    group = queue.list()[0]
    assert group.members[0].source_hash == queue.file_hash(source)
    assert group.members[0].sheet_name == "Hareketler"
    assert queue.source_integrity(group, {"banka.xlsx": source}) == (True, "Kaynak kimlikleri doğrulandı.")
    source.write_bytes(b"changed source")
    assert queue.source_integrity(group, {"banka.xlsx": source})[0] is False


def test_review_queue_rejects_stale_screen_and_keeps_transition_audit(tmp_path):
    database = tmp_path / "operations.sqlite3"
    first = ReviewQueue(database, company_id=1)
    group_id = first.enqueue([member()])
    stale_group = first.list()[0]
    current = ReviewQueue(database, company_id=1)
    current.assign(group_id, user_id=7, expected_version=stale_group.version)
    try:
        first.resolve(group_id, user_id=9, resolution_code="HAVALE", expected_version=stale_group.version)
    except ReviewQueueError as error:
        assert "başka bir kullanıcı" in str(error)
    else:
        raise AssertionError("eski ekrandaki karar güncel kaydı ezmemeli")
    events = current.events(group_id)
    assert [(event.previous_status, event.new_status) for event in events] == [("", "OPEN"), ("OPEN", "ASSIGNED")]
    assert events[-1].previous_version == 1
    assert events[-1].new_version == 2
