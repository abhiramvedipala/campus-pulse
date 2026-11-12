import pytest
from campuspulse.download import scrape_raw_zip_url


def test_scrape_picks_dated_raw_zip():
    html = '<a href="https://x.org/downloads/Most-Recent-Cohorts-Institution_11022026.zip">a</a>' \
           '<a href="https://x.org/downloads/College_Scorecard_Raw_Data_11022026.zip">b</a>'
    assert scrape_raw_zip_url(html).endswith("College_Scorecard_Raw_Data_11022026.zip")


def test_scrape_fails_loudly_when_link_missing():
    with pytest.raises(RuntimeError):
        scrape_raw_zip_url("<html>nothing here</html>")
