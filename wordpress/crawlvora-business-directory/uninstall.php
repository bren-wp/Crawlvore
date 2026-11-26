<?php
defined('WP_UNINSTALL_PLUGIN') || exit;
delete_option('crawlvora_catalog_root');
// Reviewed catalogs belong to the operator and are never deleted.
