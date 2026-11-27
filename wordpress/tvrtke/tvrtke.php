<?php
/**
 * Plugin Name: Tvrtke
 * Plugin URI: https://tvrtke.com.hr/
 * Description: Privatni poslovni imenik, uvoz CSV podataka i spremljeni odabiri.
 * Version: 0.1.0
 * Author: Brendigo
 * Author URI: https://brendigo.com/
 * Requires PHP: 8.1
 * Text Domain: tvrtke
 */
defined('ABSPATH') || exit;

final class Brendigo_Tvrtke {
    private const LIMIT = 50;
    private static function table(): string {
        global $wpdb;
        return $wpdb->prefix . 'brendigo_tvrtke';
    }
    public static function activate(): void {
        global $wpdb;
        require_once ABSPATH . 'wp-admin/includes/upgrade.php';
        $table = self::table();
        $collate = $wpdb->get_charset_collate();
        dbDelta("CREATE TABLE $table (
            mbs char(9) NOT NULL,
            oib char(11) NOT NULL DEFAULT '',
            title varchar(255) NOT NULL,
            city varchar(120) NOT NULL DEFAULT '',
            email varchar(254) NOT NULL DEFAULT '',
            saved tinyint unsigned NOT NULL DEFAULT 0,
            PRIMARY KEY  (mbs),
            KEY title (title(150)),
            KEY city (city),
            KEY oib (oib),
            KEY saved (saved,mbs)
        ) ENGINE=InnoDB $collate;");
    }
    public static function menu(): void {
        add_menu_page('Tvrtke', 'Tvrtke', 'manage_options', 'brendigo-tvrtke', [self::class,'page'], 'dashicons-building');
    }
    private static function authorize(string $action): void {
        if (!current_user_can('manage_options')) {
            wp_die('Nemate ovlaštenje.', '', ['response'=>403]);
        }
        check_admin_referer('tvrtke_'.$action);
    }
    private static function input(array $source, string $key): string {
        return isset($source[$key]) && is_string($source[$key]) ? sanitize_text_field(wp_unslash($source[$key])) : '';
    }
    private static function redirect(string $notice): void {
        wp_safe_redirect(add_query_arg(['page'=>'brendigo-tvrtke','notice'=>$notice],admin_url('admin.php')));
        exit;
    }
    private static function normalize_id(string $value, int $length): string {
        $value=trim($value);
        return preg_match('/^[0-9]{1,'.$length.'}$/D',$value) ? str_pad($value,$length,'0',STR_PAD_LEFT) : '';
    }
    public static function import(): void {
        self::authorize('import');
        global $wpdb;
        $file=$_FILES['tvrtke_csv']??null;
        if (!is_array($file) || ($file['error']??1)!==UPLOAD_ERR_OK ||
            !is_string($file['tmp_name']??null) || !is_uploaded_file($file['tmp_name']) ||
            filesize($file['tmp_name'])>10*1024*1024) {
            self::redirect('invalid');
        }
        $stream=fopen($file['tmp_name'],'rb');
        if (!$stream) self::redirect('invalid');
        $started=false;
        try {
            $header=fgetcsv($stream,65536,',','"','');
            if (!$header) throw new RuntimeException('header');
            $header=array_map(static fn($v)=>strtolower(trim((string)$v,"\xEF\xBB\xBF \t\r\n")),$header);
            if (count($header)!==count(array_unique($header)) || !in_array('mbs',$header,true) || !in_array('title',$header,true)) {
                throw new RuntimeException('header');
            }
            $table=self::table();
            // Require a transactional table rather than silently accepting a partial import.
            $engine=$wpdb->get_var($wpdb->prepare("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",$table));
            if (strtolower((string)$engine)!=='innodb' || $wpdb->query('START TRANSACTION')===false) throw new RuntimeException('transaction');
            $started=true;
            $count=0;
            while (($row=fgetcsv($stream,65536,',','"',''))!==false) {
                if ($row===[null]) continue;
                if (++$count>50000 || count($row)!==count($header)) throw new RuntimeException('rows');
                $data=array_combine($header,$row);
                $mbs=self::normalize_id((string)$data['mbs'],9);
                $title=sanitize_text_field((string)$data['title']);
                $oib=self::normalize_id((string)($data['oib']??''),11);
                $city=sanitize_text_field((string)($data['city']??''));
                $email=sanitize_email((string)($data['email']??''));
                if (!$mbs || !$title || strlen($title)>255 || strlen($city)>120 || strlen($email)>254) throw new RuntimeException('record');
                $sql=$wpdb->prepare("INSERT INTO $table (mbs,oib,title,city,email) VALUES (%s,%s,%s,%s,%s)
                    ON DUPLICATE KEY UPDATE oib=IF(VALUES(oib)='',oib,VALUES(oib)),title=VALUES(title),city=IF(VALUES(city)='',city,VALUES(city)),email=IF(VALUES(email)='',email,VALUES(email))",
                    $mbs,$oib,$title,$city,$email);
                if ($wpdb->query($sql)===false) throw new RuntimeException('database');
            }
            if (!feof($stream) || !$count || $wpdb->query('COMMIT')===false) throw new RuntimeException('commit');
            $started=false;
        } catch (Throwable $e) {
            if ($started) $wpdb->query('ROLLBACK');
            fclose($stream);
            self::redirect('invalid');
        }
        fclose($stream);
        self::redirect('imported');
    }
    public static function save(): void {
        self::authorize('save');
        global $wpdb;
        $mbs=self::input($_POST,'mbs');
        $selected=self::input($_POST,'saved');
        if (!preg_match('/^[0-9]{9}$/D',$mbs) || !in_array($selected,['0','1'],true)) self::redirect('invalid');
        if ($wpdb->update(self::table(),['saved'=>(int)$selected],['mbs'=>$mbs],['%d'],['%s'])===false) self::redirect('invalid');
        self::redirect('saved');
    }
    public static function export(): void {
        self::authorize('export');
        global $wpdb;
        nocache_headers();
        header('Content-Type: text/csv; charset=utf-8');
        header('Content-Disposition: attachment; filename="tvrtke-moj-odabir.csv"');
        header('X-Content-Type-Options: nosniff');
        $out=fopen('php://output','wb');
        fputcsv($out,['mbs','oib','title','city','email'],',','"','');
        $table=self::table();
        $cursor='';
        do {
            $rows=$wpdb->get_results($wpdb->prepare("SELECT mbs,oib,title,city,email FROM $table WHERE saved=1 AND mbs>%s ORDER BY mbs LIMIT 500",$cursor),ARRAY_A);
            foreach ($rows as $row) {
                $cursor=$row['mbs'];
                $values=array_map(static fn($v)=>preg_match('/^[\s]*[=+\-@]|\A[\t\r\n]/u',(string)$v)?"'".$v:$v,$row);
                fputcsv($out,$values,',','"','');
            }
        } while (count($rows)===500 && !connection_aborted());
        fclose($out);
        exit;
    }
    public static function page(): void {
        if (!current_user_can('manage_options')) return;
        global $wpdb;
        $q=self::input($_GET,'q');
        $city=self::input($_GET,'city');
        $saved=self::input($_GET,'saved')==='1';
        $contact=self::input($_GET,'contact')==='1';
        $after=self::input($_GET,'after');
        if (!preg_match('/^[0-9]{9}$/D',$after)) $after='';
        $table=self::table();
        $where=['mbs>%s'];$args=[$after];
        if ($q!=='') {
            $where[]='(mbs=%s OR oib=%s OR title LIKE %s)';
            array_push($args,$q,$q,$wpdb->esc_like($q).'%');
        }
        if ($city!=='') {$where[]='city=%s';$args[]=$city;}
        if ($saved) $where[]='saved=1';
        if ($contact) $where[]="email<>''";
        $rows=$wpdb->get_results($wpdb->prepare("SELECT mbs,oib,title,city,email,saved FROM $table WHERE ".implode(' AND ',$where)." ORDER BY mbs LIMIT 51",$args),ARRAY_A);
        $next=count($rows)>self::LIMIT;
        $rows=array_slice($rows,0,self::LIMIT);
        $notices=['imported'=>'Uvoz je dovršen.','saved'=>'Odabir je spremljen.','invalid'=>'Radnja nije uspjela. Provjerite CSV format ili ograničenja uvoza.'];
        echo '<div class="wrap"><h1>Tvrtke</h1><p>Privatni poslovni imenik · Brendigo</p>';
        $notice=self::input($_GET,'notice');
        if (isset($notices[$notice])) echo '<div class="notice notice-info"><p>'.esc_html($notices[$notice]).'</p></div>';
        echo '<h2>Uvoz podataka</h2><p>CSV s kolonama mbs,title te opcionalno oib,city,email; najviše 50.000 redaka i 10 MiB po uvozu.</p>';
        echo '<form method="post" enctype="multipart/form-data" action="'.esc_url(admin_url('admin-post.php')).'"><input type="hidden" name="action" value="brendigo_tvrtke_import">';
        wp_nonce_field('tvrtke_import');
        echo '<input type="file" name="tvrtke_csv" accept=".csv,text/csv" required> ';
        submit_button('Uvezi', 'primary', 'submit', false);echo '</form>';
        echo '<h2>Poslovni imenik</h2><form method="get"><input type="hidden" name="page" value="brendigo-tvrtke"><label>Naziv, OIB ili MBS <input name="q" value="'.esc_attr($q).'"></label> <label>Grad <input name="city" value="'.esc_attr($city).'"></label> <label><input type="checkbox" name="contact" value="1" '.checked($contact,true,false).'> Ima e-poštu</label> <label><input type="checkbox" name="saved" value="1" '.checked($saved,true,false).'> Moje tvrtke</label> ';
        submit_button('Pretraži','secondary','submit',false);echo '</form><table class="widefat striped"><thead><tr><th>Tvrtka</th><th>MBS</th><th>OIB</th><th>Grad</th><th>E-pošta</th><th>Odabir</th></tr></thead><tbody>';
        foreach ($rows as $row) {
            echo '<tr>';
            foreach (['title','mbs','oib','city','email'] as $field) echo '<td>'.esc_html($row[$field]).'</td>';
            echo '<td><form method="post" action="'.esc_url(admin_url('admin-post.php')).'"><input type="hidden" name="action" value="brendigo_tvrtke_save"><input type="hidden" name="mbs" value="'.esc_attr($row['mbs']).'"><input type="hidden" name="saved" value="'.($row['saved']?'0':'1').'">';
            wp_nonce_field('tvrtke_save');submit_button($row['saved']?'Ukloni':'Spremi','secondary','submit',false);
            echo '</form></td></tr>';
        }
        if (!$rows) echo '<tr><td colspan="6">Nema rezultata.</td></tr>';
        echo '</tbody></table>';
        if ($next) {
            $last=end($rows);
            echo '<p><a class="button" href="'.esc_url(add_query_arg(['page'=>'brendigo-tvrtke','q'=>$q,'city'=>$city,'saved'=>$saved?'1':'0','contact'=>$contact?'1':'0','after'=>$last['mbs']],admin_url('admin.php'))).'">Sljedeća stranica</a></p>';
        }
        echo '<form method="post" action="'.esc_url(admin_url('admin-post.php')).'"><input type="hidden" name="action" value="brendigo_tvrtke_export">';
        wp_nonce_field('tvrtke_export');submit_button('Izvezi Moje tvrtke (CSV)');echo '</form>';
        echo '<p><a href="https://tvrtke.com.hr/" target="_blank" rel="noopener noreferrer">tvrtke.com.hr</a> · <a href="https://brendigo.com/" target="_blank" rel="noopener noreferrer">Brendigo</a></p></div>';
    }
}
register_activation_hook(__FILE__,[Brendigo_Tvrtke::class,'activate']);
add_action('admin_menu',[Brendigo_Tvrtke::class,'menu']);
add_action('admin_post_brendigo_tvrtke_import',[Brendigo_Tvrtke::class,'import']);
add_action('admin_post_brendigo_tvrtke_save',[Brendigo_Tvrtke::class,'save']);
add_action('admin_post_brendigo_tvrtke_export',[Brendigo_Tvrtke::class,'export']);
