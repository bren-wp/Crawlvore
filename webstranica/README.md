# Crawlvora web — shared hosting

PHP 8.2+, Apache or compatible PHP web hosting. Upload the contents of this directory to public_html or a subdirectory. No Node, SQL server, cron, Composer or server-side JavaScript is required. Routes use index.php?view=... and work without mod_rewrite. Existing English query aliases remain supported.

The design follows the supplied company-insight-platform reference (navy/gold, editorial serif headings, homepage, services, pricing, search, about, contact and legal pages). Reference photos hero.jpg, analytics.jpg and partners.jpg belong in assets/; CSS has a graceful fallback. No fictitious profiles, testimonials, contact details, revenue, credit scores, payments, daily-update promises or subscriptions are published. Before going public, supply verified legal operator identity, privacy contact and commercial conditions. The legal pages are informational drafts, not final compliance approval.

Publish only reviewed organization records with tools/build_web_catalog.py. Keep country manifests and JSON shards under storage/data; prevent direct access to storage with server configuration. Never put desktop SQLite snapshots, credentials or personal contact data in public_html. Verify the hosting server honors storage/.htaccess. If using Nginx, configure an equivalent deny rule. No external fonts or tracking scripts are requested.

Deploy by copying site files; do not overwrite an existing approved storage/data snapshot. The public catalog remains empty until reviewed data are installed.

## Language and deployment

The shared PHP template uses English by default; Croatian is available using
lang=hr. Navigation, search forms, metadata, source descriptions, the features
page and download information support both languages. Original business data
is not translated. Verify the 28 language/page combinations with
tools/web_http_acceptance.py before deployment.

Use the code-only Crawlvora-Web.zip for a fresh installation. On an existing
installation use Crawlvora-Web-Upgrade.zip, which deliberately omits every
storage/data member and, unless a base URL is supplied, robots.txt and SEO
configuration. Back up the hosting site before upgrading.

To generate sitemap.xml, robots.txt and absolute canonical/hreflang URLs, run
the package tool from a committed source checkout with --base-url set to your
actual HTTPS site base (including any hosting subdirectory):

    python tools/package_web.py Crawlvora-Web.zip --ref HEAD --base-url https://example.invalid/catalog/

The example domain is a placeholder, not a configured production domain.
Use --upgrade for an existing installation. No Python or extra service is
required on the hosting server. Without a real configured URL the website
omits absolute canonical and hreflang links rather than guessing a domain.
Search/filter variants and error pages are noindex. Check storage access
rules independently on your actual Apache or Nginx server.

For subdirectory hosting, merge the generated robots rules and sitemap URL into the domain-root robots.txt; crawlers do not treat a subdirectory robots.txt as authoritative.

Company profiles use the exact published registration identifier, country and entity type. Missing or ambiguous profiles are not synthesized. Profiles are noindex and omit private catalog fields.


### Nginx deployment acceptance

The Apache storage .htaccess does not apply to Nginx. Configure an explicit
deny location at the actual deployed path, including any URL prefix:

    location = /storage { deny all; }
    location ^~ /storage/ { deny all; }

For a subdirectory deployment, use its prefix in both locations. Restrict
PHP execution to the public entry point and do not expose catalog files
through aliases, backup paths or symlinks. Do not expose a PHP CLI
development server to the Internet. The disposable CI test uses an actual
Nginx reverse proxy with an isolated PHP CLI upstream and checks normalized
storage URLs. Actual PHP-FPM, TLS, domain, filesystem permissions and
operator hosting configuration must be separately verified before deployment.
