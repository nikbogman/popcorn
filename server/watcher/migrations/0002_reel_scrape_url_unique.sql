-- One scrape per reel: keep each URL's newest request, then let an index hold that.
delete from reel_scrape a using reel_scrape b where a.url = b.url and (a.created_at, a.id) < (b.created_at, b.id);
create unique index reel_scrape_url on reel_scrape (url);
