<?php
declare(strict_types=1);
namespace Crawlvora\Directory;

defined('ABSPATH') || exit;

final class Catalog {
    public const KINDS = ['company','entrepreneur','institution','nonprofit','unknown'];
    public const COUNTRIES = ['HR','GB'];

    public static function private_root(string $path): ?string {
        if ($path === '' || str_contains($path, "\0")) { return null; }
        $root = realpath($path);
        if ($root === false || !is_dir($root) || !is_readable($root)) { return null; }
        $root = rtrim(str_replace('\\','/',$root),'/');
        if ($root === '' || preg_match('/^[A-Za-z]:$/D',$root)) { return null; }
        foreach ([ABSPATH, (string) ($_SERVER['DOCUMENT_ROOT'] ?? '')] as $public) {
            if ($public === '') { continue; }
            $public = realpath($public);
            if ($public === false) { continue; }
            $public = rtrim(str_replace('\\','/',$public),'/');
            $a = PHP_OS_FAMILY === 'Windows' ? strtolower($root) : $root;
            $b = PHP_OS_FAMILY === 'Windows' ? strtolower($public) : $public;
            if ($a === $b || str_starts_with($a,$b.'/') || str_starts_with($b,$a.'/')) { return null; }
        }
        return $root;
    }

    private static function read(string $root,string $relative,int $max): array {
        $file = realpath($root.'/'.$relative);
        if ($file === false || !str_starts_with(str_replace('\\','/',$file),$root.'/') || !is_file($file) || !is_readable($file)) {
            throw new \RuntimeException('Catalog unavailable.');
        }
        $size = filesize($file);
        if ($size === false || $size < 1 || $size > $max) { throw new \RuntimeException('Invalid catalog file size.'); }
        $raw = file_get_contents($file,false,null,0,$max+1);
        if ($raw === false || strlen($raw)>$max) { throw new \RuntimeException('Catalog unavailable.'); }
        $data = json_decode($raw,true,32,JSON_THROW_ON_ERROR);
        if (!is_array($data)) { throw new \RuntimeException('Invalid catalog.'); }
        return $data;
    }

    public static function manifest(string $root,string $country): array {
        if (!in_array($country,self::COUNTRIES,true)) { throw new \RuntimeException('Invalid country.'); }
        $m = self::read($root,$country.'/manifest.json',4*1024*1024);
        if (($m['country']??null)!==$country || !is_int($m['count']??null) || $m['count']<0 ||
            !is_array($m['shards']??null) || !array_is_list($m['shards']) || count($m['shards'])>20000) {
            throw new \RuntimeException('Invalid manifest.');
        }
        return $m;
    }

    private static function fold(string $s): string {
        return function_exists('mb_strtolower') ? mb_strtolower($s,'UTF-8') :
            strtolower(strtr($s,['Č'=>'č','Ć'=>'ć','Ž'=>'ž','Š'=>'š','Đ'=>'đ']));
    }

    public static function search(string $root,string $country,string $kind,string $q,int $page): array {
        if (($kind!==''&&!in_array($kind,self::KINDS,true)) || strlen($q)>200 || $page<1 || $page>10000) {
            throw new \RuntimeException('Invalid search.');
        }
        $m=self::manifest($root,$country);
        $query=self::fold($q);$digits=str_replace([' ','-'],'',$q);
        $numeric=preg_match('/^[0-9]{1,11}$/D',$digits)===1;
        $skip=($page-1)*25;$seen=0;$rows=[];$deadline=microtime(true)+5;
        foreach ($m['shards'] as $shard) {
            if (microtime(true)>$deadline) { throw new \RuntimeException('Search limit reached.'); }
            if (!is_string($shard) || !preg_match('/^'.preg_quote($country,'/').'-(company|entrepreneur|institution|nonprofit|unknown)-[0-9]{6}\.json$/D',$shard,$match)) {
                throw new \RuntimeException('Invalid shard.');
            }
            if ($kind!=='' && $kind!==$match[1]) { continue; }
            $records=self::read($root,$country.'/'.$shard,2*1024*1024);
            if (!array_is_list($records) || count($records)>500) { throw new \RuntimeException('Invalid shard records.'); }
            foreach ($records as $record) {
                if (!is_array($record)||($record['country']??null)!==$country||($record['kind']??null)!==$match[1]||
                    !is_string($record['name']??null)||strlen($record['name'])>2000||!is_string($record['as_of']??null)||
                    !preg_match('/^\d{4}-\d{2}-\d{2}$/D',$record['as_of'])) { throw new \RuntimeException('Invalid record.'); }
                $row=['name'=>$record['name'],'country'=>$country,'kind'=>$match[1],'as_of'=>$record['as_of']];
                foreach (['registration_number','tax_number','city'] as $key) {
                    $value=$record[$key]??'';
                    if (!is_string($value)||strlen($value)>400) { throw new \RuntimeException('Invalid field.'); }
                    if ($key==='tax_number' && in_array($match[1],['entrepreneur','unknown'],true)) { $value=''; }
                    $row[$key]=$value;
                }
                if ($query!=='') {
                    $found=str_contains(self::fold($row['name']),$query);
                    if ($numeric) {
                        $found=$row['registration_number']===$digits||$row['tax_number']===$digits;
                        if ($country==='HR' && strlen($digits)<=9 && preg_match('/^[0-9]{1,9}$/D',$row['registration_number'])) {
                            $found=$found||ltrim($row['registration_number'],'0')===ltrim($digits,'0');
                        }
                    } else {
                        $found=$found||self::fold($row['registration_number'])===$query||self::fold($row['tax_number'])===$query;
                    }
                    if (!$found) { continue; }
                }
                if ($seen++<$skip) { continue; }
                if (count($rows)===25) { return ['rows'=>$rows,'next'=>true,'count'=>$m['count']]; }
                $rows[]=$row;
            }
        }
        return ['rows'=>$rows,'next'=>false,'count'=>$m['count']];
    }
}
