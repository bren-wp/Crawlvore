=== Crawlvora Business Directory ===
Contributors: crawlvora
Tags: business directory, company search, Croatia, United Kingdom
Requires at least: 6.5
Requires PHP: 8.2
Stable tag: 1.0.0
License: GPL-2.0-or-later
License URI: https://www.gnu.org/licenses/old-licenses/gpl-2.0.html

== Description ==
A responsive, local business directory for WordPress. Search reviewed Croatian and British organization records by name, registration number or published tax identifier. Country and entity classification filters are included. No external scripts, tracking, additional SQL tables, cron or desktop credentials.

== Installation ==
1. Install Crawlvora-WordPress.zip in Plugins > Add New > Upload Plugin and activate.
2. Prepare reviewed JSON snapshots with the Crawlvora tools/build_web_catalog.py utility. Keep the HR and GB folders in a dedicated readable directory outside the public web root, not in wp-content/uploads. Ensure the directory is not exposed by any server alias.
3. Open Settings > Crawlvora and save that absolute directory.
4. Add [crawlvora_directory] to a page or post. Optional initial country: [crawlvora_directory country="GB"].
5. Verify the live hosting permissions, search performance and applicable operator/privacy information before public launch.

The plugin is empty until reviewed catalogs are supplied. It does not automatically acquire or publish raw registry data. No fictitious records are included. The data directory is never modified by the plugin. Normal WordPress database infrastructure is still required. Source and reuse terms appear in a collapsible provenance section.

== Changelog ==
= 1.0.0 =
* Local JSON catalog search, settings and shortcode.
