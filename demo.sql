-- vgi-laya Demo: the Query.farm Hacker News filter, locally
-- =========================================================
-- Same query as the TypeSafe/VGI writeup — score new HN stories by taste —
-- but Laya runs on your machine. No API key, no cloud.

FORCE INSTALL vgi FROM community;
LOAD vgi;

ATTACH 'hackernews' (TYPE vgi,
  LOCATION 'uvx --from git+https://github.com/Query-farm/vgi-hackernews vgi-hackernews');

-- From this repo. Published package: uvx --from git+https://github.com/lmangani/vgi-laya vgi-laya
ATTACH 'laya' (TYPE vgi, LOCATION 'uv run laya_worker.py');

SELECT title, url, interesting.noul
FROM
  (SELECT title, url FROM hackernews.new_stories LIMIT 500) hn_stories,
  LATERAL laya.main.noul(
    hn_stories.title,
    instructions => 'Is this story interesting to someone who in data and databases
                    (i.e. DuckDB) but also appreciates distributed systems, python,
                    apache arrow'
  ) interesting
WHERE interesting.noul > 0.50
ORDER BY interesting.noul DESC
LIMIT 20;
