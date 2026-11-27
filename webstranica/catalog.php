<?php
declare(strict_types=1);
const DATA = __DIR__ . '/storage/data';
const TYPES = ['company'=>'Companies','entrepreneur'=>'Entrepreneurs','institution'=>'Institutions','nonprofit'=>'Nonprofit organizations','unknown'=>'Unclassified'];
function read_json(string $file, int $max=4194304): array {
    // A long-running PHP process must not trust a cached pre-replacement path.
    clearstatcache(true);
    $cursor=str_replace('\\','/',$file);
    $site=str_replace('\\','/',__DIR__);
    while ($cursor!==$site) {
        if (is_link($cursor)) throw new RuntimeException('Catalog unavailable');
        $parent=str_replace('\\','/',dirname($cursor));
        if ($parent===$cursor) throw new RuntimeException('Catalog unavailable');
        $cursor=$parent;
    }
    $root=realpath(__DIR__);
    $resolved=realpath($file);
    if ($root===false || $resolved===false || !is_file($resolved) || !is_readable($resolved)) throw new RuntimeException('Catalog unavailable');
    $root=str_replace('\\','/',$root);
    $normalized=str_replace('\\','/',$resolved);
    $expected=str_replace('\\','/',$file);
    if (PHP_OS_FAMILY==='Windows') {$root=strtolower($root);$normalized=strtolower($normalized);$expected=strtolower($expected);}
    if ($normalized!==$expected || !str_starts_with($normalized,rtrim($root,'/').'/')) throw new RuntimeException('Catalog unavailable');
    $file=$resolved;
    $size=filesize($file);
    if ($size===false || $size<1 || $size>$max) throw new RuntimeException('Invalid catalog file size');
    $raw=file_get_contents($file,false,null,0,$max+1);
    if ($raw===false || strlen($raw)>$max) throw new RuntimeException('Catalog unavailable');
    $data=json_decode($raw,true,32,JSON_THROW_ON_ERROR);
    if (!is_array($data)) throw new RuntimeException('Invalid catalog');
    return $data;
}
function param(string $key, string $default=''): string {
    $value=$_GET[$key]??$default;
    return is_string($value) ? trim($value) : $default;
}
function h(string|int|null $value): string { return htmlspecialchars((string)$value,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8'); }
function fold(string $value): string {
    return function_exists('mb_strtolower') ? mb_strtolower($value,'UTF-8') : strtolower(strtr($value,['Č'=>'č','Ć'=>'ć','Ž'=>'ž','Š'=>'š','Đ'=>'đ','Á'=>'á','É'=>'é','Í'=>'í','Ó'=>'ó','Ö'=>'ö','Ő'=>'ő','Ú'=>'ú','Ü'=>'ü','Ű'=>'ű']));
}
function search_catalog(array $manifest,string $q,string $country,string $kind,int $page,bool $exact_registration=false): array {
    if (!in_array($country,['HR','GB'],true) || ($kind!==''&&!isset(TYPES[$kind])) || strlen($q)>200 || $page<1 || $page>10000) throw new RuntimeException('Invalid search');
    $query=fold($q); $digits=preg_replace('/[ -]/','',$q);
    $numeric=preg_match('/^[0-9]{1,11}$/D',$digits)===1;
    $skip=($page-1)*25; $results=[]; $seen=0;
    if (($manifest['country']??null)!==$country || !is_int($manifest['count']??null) || $manifest['count']<0 || !is_array($manifest['shards']??null) || !array_is_list($manifest['shards']) || count($manifest['shards'])>20000) throw new RuntimeException('Invalid manifest');
    $deadline=microtime(true)+5;
    foreach ($manifest['shards'] as $shard) {
        if (microtime(true)>$deadline) throw new RuntimeException('Search limit reached');
        if (!is_string($shard) || !preg_match('/^'.preg_quote($country,'/').'-(company|entrepreneur|institution|nonprofit|unknown)-[0-9]{6}\.json$/D',$shard,$match)) throw new RuntimeException('Invalid shard');
        if ($kind!=='' && $kind!==$match[1]) continue;
        $records=read_json(DATA.'/'.$country.'/'.$shard,2097152);
        if (!array_is_list($records) || count($records)>500) throw new RuntimeException('Invalid shard records');
        foreach ($records as $record) {
            if (!is_array($record) || ($record['country']??null)!==$country || ($record['kind']??null)!==$match[1] || !is_string($record['name']??null) || strlen($record['name'])>2000 || !is_string($record['as_of']??null) || !preg_match('/^\d{4}-\d{2}-\d{2}$/D',$record['as_of'])) throw new RuntimeException('Invalid record');
            foreach (['registration_number','tax_number','city'] as $field) {
                if (isset($record[$field]) && (!is_string($record[$field]) || strlen($record[$field])>400)) throw new RuntimeException('Invalid field');
            }
            if (in_array($record['kind'],['entrepreneur','unknown'],true)) unset($record['tax_number']);
            $record=array_intersect_key($record,array_flip(['country','kind','name','as_of','registration_number','tax_number','city']));
            if ($exact_registration) {
                if (fold($record['registration_number']??'')!==$query) continue;
            } elseif ($query!=='') {
                $found=str_contains(fold($record['name']),$query);
                if ($numeric) {
                    $found=false;
                    foreach (['registration_number','tax_number'] as $key) {
                        $v=$record[$key]??'';
                        if ($v!=='' && ($v===$digits || ($key==='registration_number' && $record['country']==='HR' && strlen($digits)<=9 && preg_match('/^[0-9]{1,9}$/D',$v) && ltrim($v,'0')===ltrim($digits,'0')))) $found=true;
                    }
                } else {
                    $found=$found || fold($record['registration_number']??'')===$query || fold($record['tax_number']??'')===$query;
                }
                if (!$found) continue;
            }
            if ($seen++<$skip) continue;
            if (count($results)===25) return ['records'=>$results,'next'=>true];
            $results[]=$record;
        }
    }
    return ['records'=>$results,'next'=>false];
}
function query_link(array $values): string { return '?'.http_build_query($values,'','&',PHP_QUERY_RFC3986); }

function registration_valid(string $id): bool {
    return preg_match('/^[A-Za-z0-9][A-Za-z0-9-]{0,39}$/D',$id)===1;
}
function company_profile(array $manifest,string $country,string $kind,string $id): ?array {
    if (!registration_valid($id)||!isset(TYPES[$kind])) return null;
    $result=search_catalog($manifest,$id,$country,$kind,1,true);
    return count($result['records'])===1 && !$result['next']?$result['records'][0]:null;
}
