# Hot & Spicy Starfleet Command forum reference

This directory describes a local, read-only archive of the public Starfleet Command category at:

https://hotandspicyforums.com/starfleet-command-f3/

The archive intentionally covers all Starfleet Command games because launcher, networking, protocol,
modding, compatibility, and server observations may apply across titles. Run the crawler from the
repository root:

```powershell
python tools/archive_hotandspicy.py
```

Raw HTML, crawl state, manifests, and extracted link inventories are ignored by Git. The crawler is
resumable, stays within the public Starfleet Command category and its discovered topic pages, removes
session IDs, and waits between requests. It inventories attachment/media and external-download URLs
but does not execute or automatically download unknown files.

This material is reference evidence only. Server-kit files and validated protocol observations remain
the implementation authorities.

## Local snapshot

The 2026-09-08 crawl archived 313 HTML pages (32,433,485 bytes): 309 paginated topic pages covering
81 publicly accessible topic IDs, plus category/forum pages. It inventoried 44 media or attachment
URLs and 1,404 external links. Two linked legacy topics returned HTTP 404; their URLs and errors are
retained in the ignored manifest. Re-running the crawler resumes from its saved state without
redownloading completed URLs.
