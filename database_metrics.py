from db import query, query_one


def get_metrics():
    import os
    from datetime import datetime, timedelta

    metrics = {}
    # Total users
    row = query_one("SELECT COUNT(*) FROM users")
    metrics["total_users"] = row[0] if row else 0
    # Total comparisons
    row = query_one("SELECT COUNT(*) FROM comparisons")
    metrics["total_comparisons"] = row[0] if row else 0
    # Total images
    row = query_one("SELECT COUNT(*) FROM image_positions")
    metrics["total_images"] = row[0] if row else 0
    # Active users (last 7 days)
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    row = query_one(
        "SELECT COUNT(DISTINCT user_id) FROM comparisons WHERE created_at >= ?",
        (week_ago,),
    )
    metrics["active_users_7d"] = row[0] if row else 0
    # Comparisons created in last 7 days
    row = query_one(
        "SELECT COUNT(*) FROM comparisons WHERE created_at >= ?",
        (week_ago,),
    )
    metrics["comparisons_7d"] = row[0] if row else 0

    # --- Date-based metrics for last 14 days ---
    days = 14
    today = datetime.now().date()
    date_labels = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in reversed(range(days))]

    # Users registered per day
    user_rows = query(
        """
        SELECT DATE(created_at), COUNT(*) FROM users
        WHERE created_at >= ?
        GROUP BY DATE(created_at)
        """,
        ((today - timedelta(days=days - 1)).strftime("%Y-%m-%d"),),
    )
    user_counts = dict(user_rows)
    metrics["users_per_day"] = [user_counts.get(date, 0) for date in date_labels]

    # Comparisons created per day
    comp_rows = query(
        """
        SELECT DATE(created_at), COUNT(*) FROM comparisons
        WHERE created_at >= ?
        GROUP BY DATE(created_at)
        """,
        ((today - timedelta(days=days - 1)).strftime("%Y-%m-%d"),),
    )
    comp_counts = dict(comp_rows)
    metrics["comparisons_per_day"] = [comp_counts.get(date, 0) for date in date_labels]

    # Images uploaded per day (by image_positions join comparisons for date)
    img_rows = query(
        """
        SELECT DATE(c.created_at), COUNT(ip.filename)
        FROM image_positions ip
        JOIN comparisons c ON ip.comparison_id = c.id
        WHERE c.created_at >= ?
        GROUP BY DATE(c.created_at)
        """,
        ((today - timedelta(days=days - 1)).strftime("%Y-%m-%d"),),
    )
    img_counts = dict(img_rows)
    metrics["images_per_day"] = [img_counts.get(date, 0) for date in date_labels]

    metrics["date_labels"] = date_labels

    # Total image size on disk (sum of all files in uploads/)

    uploads_dir = os.getenv("UPLOADS_PATH", "uploads")
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(uploads_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.isfile(fp):
                total_size += os.path.getsize(fp)
    metrics["total_images_size_bytes"] = total_size
    metrics["total_images_humansize"] = format_bytes(total_size)

    return metrics


def format_bytes(bytes):
    if bytes < 1024:
        return f"{bytes} B"
    elif bytes < 1024 * 1024:
        return f"{(bytes / 1024):.2f} KB"
    elif bytes < 1024 * 1024 * 1024:
        return f"{(bytes / (1024 * 1024)):.2f} MB"
    else:
        return f"{(bytes / (1024 * 1024 * 1024)):.2f} GB"
