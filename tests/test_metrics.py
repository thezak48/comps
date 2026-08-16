import database
import database_metrics


def test_format_bytes_and_size_parser():
    assert database_metrics.format_bytes(12) == "12 B"
    assert database_metrics.format_bytes(1024) == "1.00 KB"
    assert database_metrics.format_bytes(1024 * 1024) == "1.00 MB"
    assert database_metrics.format_bytes(1024 * 1024 * 1024) == "1.00 GB"
    assert database_metrics._parse_image_size_bytes("123 bytes") == 123
    assert database_metrics._parse_image_size_bytes("bad") == 0


def test_metrics_report_database_and_local_storage(isolated_db, tmp_path, monkeypatch):
    comparison_id = "66666666-6666-6666-6666-666666666666"
    database.create_comparison(comparison_id, "Metrics", None, [], {}, None)
    database.store_image_position(comparison_id, "image.png", 0, 0)
    uploads = tmp_path / "metric-uploads" / comparison_id
    uploads.mkdir(parents=True)
    (uploads / "image.png").write_bytes(b"12345")
    monkeypatch.setenv("UPLOADS_PATH", str(tmp_path / "metric-uploads"))
    monkeypatch.setattr(database_metrics, "is_s3_enabled", lambda: False)

    metrics = database_metrics.get_metrics()

    assert metrics["total_users"] == 1
    assert metrics["total_comparisons"] == 1
    assert metrics["total_images"] == 1
    assert metrics["total_images_size_bytes"] == 5
    assert metrics["total_images_humansize"] == "5 B"
    assert len(metrics["date_labels"]) == 14
    assert len(metrics["comparisons_per_day"]) == 14


def test_metrics_sum_s3_metadata_sizes(isolated_db, monkeypatch):
    comparison_id = "77777777-7777-7777-7777-777777777777"
    database.create_comparison(comparison_id, "S3", None, [], {}, None)
    database.store_image_metadata(comparison_id, "one.png", "one.png", "10 bytes")
    database.store_image_metadata(comparison_id, "two.png", "two.png", "invalid")
    monkeypatch.setattr(database_metrics, "is_s3_enabled", lambda: True)

    metrics = database_metrics.get_metrics()

    assert metrics["total_images_size_bytes"] == 10
