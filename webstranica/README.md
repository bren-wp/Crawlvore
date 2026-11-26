# Crawlvora web — shared hosting

PHP 8.2+, Apache or compatible PHP web hosting. Upload the contents of this directory to public_html or a subdirectory. No Node, SQL server, cron, Composer or server-side JavaScript is required. Routes use index.php?view=... and work without mod_rewrite. Existing English query aliases remain supported.

The design follows the supplied company-insight-platform reference (navy/gold, editorial serif headings, homepage, services, pricing, search, about, contact and legal pages). Reference photos hero.jpg, analytics.jpg and partners.jpg belong in assets/; CSS has a graceful fallback. No fictitious profiles, testimonials, contact details, revenue, credit scores, payments, daily-update promises or subscriptions are published. Before going public, supply verified legal operator identity, privacy contact and commercial conditions. The legal pages are informational drafts, not final compliance approval.

Publish only reviewed organization records with tools/build_web_catalog.py. Keep country manifests and JSON shards under storage/data; prevent direct access to storage with server configuration. Never put desktop SQLite snapshots, credentials or personal contact data in public_html. Verify the hosting server honors storage/.htaccess. If using Nginx, configure an equivalent deny rule. No external fonts or tracking scripts are requested.

Deploy by copying site files; do not overwrite an existing approved storage/data snapshot. The public catalog remains empty until reviewed data are installed.
