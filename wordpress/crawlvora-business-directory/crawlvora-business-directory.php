<?php
/**
 * Plugin Name: Crawlvora Business Directory
 * Description: Publish a reviewed Croatian and United Kingdom business directory with privacy-conscious local JSON search.
 * Version: 1.0.0
 * Requires at least: 6.5
 * Requires PHP: 8.2
 * Author: Crawlvora
 * Text Domain: crawlvora-business-directory
 * License: GPL-2.0-or-later
 */
declare(strict_types=1);
namespace Crawlvora\Directory;
defined('ABSPATH') || exit;
require_once __DIR__.'/includes/class-catalog.php';

const OPTION = 'crawlvora_catalog_root';
const DOMAIN = 'crawlvora-business-directory';

function settings(): void {
    register_setting('crawlvora_directory',OPTION,[
        'type'=>'string','default'=>'','show_in_rest'=>false,
        'sanitize_callback'=>__NAMESPACE__.'\\sanitize_root',
    ]);
    add_settings_section('crawlvora_storage',__('Catalog storage',DOMAIN),static function():void {
        echo '<p>'.esc_html__('Use a reviewed JSON catalog stored outside the public web directory. No desktop credentials or raw private records.',DOMAIN).'</p>';
    },'crawlvora-directory');
    add_settings_field(OPTION,__('Private catalog directory',DOMAIN),static function():void {
        printf('<input class="regular-text" type="text" name="%s" value="%s" autocomplete="off">',esc_attr(OPTION),esc_attr((string)get_option(OPTION,'')));
    },'crawlvora-directory','crawlvora_storage');
}
function sanitize_root($value): string {
    if (!is_string($value)) { return (string)get_option(OPTION,''); }
    if (trim($value)==='') { return ''; }
    $root=Catalog::private_root(trim($value));
    if ($root===null) {
        add_settings_error(OPTION,'invalid-root',__('Choose a readable directory outside the public web root.',DOMAIN));
        return (string)get_option(OPTION,'');
    }
    return $root;
}
function admin_menu(): void {
    add_options_page(__('Crawlvora Directory',DOMAIN),__('Crawlvora',DOMAIN),'manage_options','crawlvora-directory',__NAMESPACE__.'\\admin_page');
}
function admin_page(): void {
    if (!current_user_can('manage_options')) { return; }
    echo '<div class="wrap"><h1>'.esc_html__('Crawlvora Business Directory',DOMAIN).'</h1>';
    echo '<p>'.esc_html__('Add [crawlvora_directory] to a page or post. Use [crawlvora_directory country="HR"] or country="GB" to set its initial country.',DOMAIN).'</p>';
    settings_errors(OPTION);
    echo '<form action="options.php" method="post">';
    settings_fields('crawlvora_directory');
    do_settings_sections('crawlvora-directory');
    submit_button();
    echo '</form>';
    $root=Catalog::private_root((string)get_option(OPTION,''));
    if ($root!==null) {
        foreach (Catalog::COUNTRIES as $country) {
            try {
                $m=Catalog::manifest($root,$country);
                printf('<p>%s: %s %s</p>',esc_html($country),esc_html(number_format_i18n($m['count'])),esc_html__('published records',DOMAIN));
            } catch (\Throwable $e) {
                printf('<p>%s: %s</p>',esc_html($country),esc_html__('Catalog not available',DOMAIN));
            }
        }
    }
    echo '</div>';
}
function query_value(string $key,string $default=''): string {
    $raw=$_GET[$key]??$default;
    return is_string($raw)?sanitize_text_field(wp_unslash($raw)):$default;
}
function assets(): void {
    wp_register_style('crawlvora-directory',plugins_url('assets/directory.css',__FILE__),[],'1.0.0');
    if (is_singular()) {
        $post=get_queried_object();
        if ($post instanceof \WP_Post && has_shortcode($post->post_content,'crawlvora_directory')) {
            wp_enqueue_style('crawlvora-directory');
        }
    }
}
function directory_shortcode($attributes=[]): string {
    $attributes=shortcode_atts(['country'=>'HR'],(array)$attributes,'crawlvora_directory');
    $initial=in_array($attributes['country'],Catalog::COUNTRIES,true)?$attributes['country']:'HR';
    $country=query_value('cv_country',$initial);
    if (!in_array($country,Catalog::COUNTRIES,true)) { $country=$initial; }
    $kind=query_value('cv_kind');
    if (!in_array($kind,Catalog::KINDS,true)) { $kind=''; }
    $q=substr(query_value('cv_q'),0,200);
    $page=max(1,min(10000,(int)query_value('cv_page','1')));
    $labels=['company'=>__('Companies',DOMAIN),'entrepreneur'=>__('Entrepreneurs',DOMAIN),'institution'=>__('Institutions',DOMAIN),'nonprofit'=>__('Nonprofit organizations',DOMAIN),'unknown'=>__('Unclassified',DOMAIN)];
    $root=Catalog::private_root((string)get_option(OPTION,''));
    $url=get_permalink();
    if (!$url) { $url=home_url('/'); }
    $route=[];
    parse_str((string)wp_parse_url($url,PHP_URL_QUERY),$route);
    $id=wp_unique_id('cv-search-');
    wp_enqueue_style('crawlvora-directory');
    ob_start();
    ?>
    <section class="cv-directory" aria-label="<?php echo esc_attr__('Business directory',DOMAIN); ?>">
      <header><span class="cv-brand">Crawlvora</span><h2><?php echo esc_html__('Business directory',DOMAIN); ?></h2></header>
      <form class="cv-filters" method="get" action="<?php echo esc_url($url); ?>">
        <?php foreach (['page_id','p','pagename'] as $key): if (isset($route[$key])&&is_scalar($route[$key])): ?>
          <input type="hidden" name="<?php echo esc_attr($key); ?>" value="<?php echo esc_attr((string)$route[$key]); ?>">
        <?php endif; endforeach; ?>
        <label for="<?php echo esc_attr($id); ?>"><?php echo esc_html__('Company name or registration identifier',DOMAIN); ?>
          <input id="<?php echo esc_attr($id); ?>" name="cv_q" maxlength="200" type="search" value="<?php echo esc_attr($q); ?>">
        </label>
        <label><?php echo esc_html__('Country',DOMAIN); ?><select name="cv_country">
          <option value="HR" <?php selected($country,'HR'); ?>><?php echo esc_html__('Croatia',DOMAIN); ?></option>
          <option value="GB" <?php selected($country,'GB'); ?>><?php echo esc_html__('United Kingdom',DOMAIN); ?></option>
        </select></label>
        <label><?php echo esc_html__('Entity type',DOMAIN); ?><select name="cv_kind">
          <option value=""><?php echo esc_html__('All types',DOMAIN); ?></option>
          <?php foreach ($labels as $value=>$label): ?><option value="<?php echo esc_attr($value); ?>" <?php selected($kind,$value); ?>><?php echo esc_html($label); ?></option><?php endforeach; ?>
        </select></label>
        <button type="submit"><?php echo esc_html__('Search',DOMAIN); ?></button>
      </form>
      <?php
      try {
          if ($root===null) { throw new \RuntimeException('Not configured.'); }
          $result=Catalog::search($root,$country,$kind,$q,$page);
          ?>
          <p class="cv-meta"><?php echo esc_html(number_format_i18n($result['count']).' '.__('published records in this catalog',DOMAIN)); ?></p>
          <?php if (!$result['rows']): ?><p><?php echo esc_html__('No matching published records. A missing result does not mean the business does not exist.',DOMAIN); ?></p><?php endif; ?>
          <div class="cv-results"><?php foreach ($result['rows'] as $record): ?>
            <article><h3><?php echo esc_html($record['name']); ?></h3><p><?php echo esc_html($labels[$record['kind']]); ?> · <?php echo esc_html($record['city']); ?></p>
            <dl><?php foreach (['registration_number'=>__('Registration number',DOMAIN),'tax_number'=>__('Tax identifier',DOMAIN),'as_of'=>__('Data date',DOMAIN)] as $key=>$label): ?>
              <dt><?php echo esc_html($label); ?></dt><dd><?php echo esc_html($record[$key]!==''?$record[$key]:__('Not published',DOMAIN)); ?></dd>
            <?php endforeach; ?></dl></article>
          <?php endforeach; ?></div>
          <nav class="cv-pagination" aria-label="<?php echo esc_attr__('Search results pages',DOMAIN); ?>">
          <?php $args=['cv_country'=>$country,'cv_kind'=>$kind,'cv_q'=>$q]; ?>
          <?php if ($page>1): ?><a href="<?php echo esc_url(add_query_arg($args+['cv_page'=>$page-1],$url)); ?>"><?php echo esc_html__('Previous',DOMAIN); ?></a><?php endif; ?>
          <span><?php echo esc_html(sprintf(__('Page %d',DOMAIN),$page)); ?></span>
          <?php if ($result['next']&&$page<10000): ?><a href="<?php echo esc_url(add_query_arg($args+['cv_page'=>$page+1],$url)); ?>"><?php echo esc_html__('Next',DOMAIN); ?></a><?php endif; ?>
          </nav>
      <?php } catch (\Throwable $e) { ?>
          <p role="status"><?php echo esc_html__('The catalog or search is temporarily unavailable. Try a more specific query or contact the site operator.',DOMAIN); ?></p>
      <?php } ?>
      <details class="cv-provenance"><summary><?php echo esc_html__('Data provenance',DOMAIN); ?></summary>
      <p><?php echo esc_html__('Only reviewed published records are shown. Verify current details with the relevant official register.',DOMAIN); ?></p>
      <a href="<?php echo esc_url($country==='HR'?'https://sudreg-data.gov.hr/':'https://download.companieshouse.gov.uk/en_output.html'); ?>" rel="noopener noreferrer"><?php echo esc_html__('Official register',DOMAIN); ?></a>
      · <a href="<?php echo esc_url($country==='HR'?'https://data.gov.hr/otvorena-dozvola':'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/'); ?>" rel="noopener noreferrer"><?php echo esc_html__('Reuse terms',DOMAIN); ?></a>
      </details>
    </section>
    <?php
    return (string)ob_get_clean();
}
add_action('admin_init',__NAMESPACE__.'\\settings');
add_action('admin_menu',__NAMESPACE__.'\\admin_menu');
add_action('wp_enqueue_scripts',__NAMESPACE__.'\\assets');
add_shortcode('crawlvora_directory',__NAMESPACE__.'\\directory_shortcode');
