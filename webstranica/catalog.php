<?php
declare(strict_types=1);
const DATA = __DIR__ . '/storage/data';
const TYPES = ['company'=>'Companies','entrepreneur'=>'Entrepreneurs','institution'=>'Institutions','nonprofit'=>'Nonprofit organizations','unknown'=>'Unclassified'];
function read_json(string $file, int $max=4194304): array {
    if (!is_file($file)) throw new RuntimeException('Catalog unavailable');
    $size=filesize($file);
    if ($size===false || $size<1 || $size>$max) throw new RuntimeException('Invalid catalog file size');
    $raw=file_get_contents($file,false,null,0,$max+1);
    if ($raw===false || strlen($raw)>$max) throw new RuntimeException('Catalog unavailable');
    $data=json_decode($raw,true,64,JSON_THROW_ON_ERROR);
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
function search_catalog(array $manifest,string $q,string $country,string $kind,int $page): array {
    if (!in_array($country,['HR','GB'],true)) throw new RuntimeException('Country required');
    $query=fold($q); $digits=preg_replace('/[ -]/','',$q);
    $numeric=preg_match('/^[0-9]{1,11}$/D',$digits)===1;
    $skip=($page-1)*25; $results=[]; $seen=0;
    if (($manifest['country']??null)!==$country || !is_int($manifest['count']??null) || $manifest['count']<0 || !is_array($manifest['shards']??null) || !array_is_list($manifest['shards']) || count($manifest['shards'])>20000) throw new RuntimeException('Invalid manifest');
    $deadline=microtime(true)+5;
    foreach ($manifest['shards'] as $shard) {
        if (microtime(true)>$deadline) throw new RuntimeException('Search limit reached');
        if (!is_string($shard) || !preg_match('/^[A-Z]{2}-(company|entrepreneur|institution|nonprofit|unknown)-[0-9]{6}\.json$/D',$shard)) throw new RuntimeException('Invalid shard');
        if ($country!=='' && !str_starts_with($shard,$country.'-')) continue;
        if ($kind!=='' && !str_contains($shard,'-'.$kind.'-')) continue;
        $records=read_json(DATA.'/'.$country.'/'.$shard,2097152);
        if (!array_is_list($records) || count($records)>500) throw new RuntimeException('Invalid shard records');
        foreach ($records as $record) {
            if (!is_array($record) || ($record['country']??null)!==$country || !isset(TYPES[$record['kind']??'']) || !str_contains($shard,'-'.$record['kind'].'-') || !is_string($record['name']??null) || strlen($record['name'])>2000 || !is_string($record['as_of']??null)) throw new RuntimeException('Invalid record');
            foreach (['registration_number','tax_number','city'] as $field) {
                if (isset($record[$field]) && (!is_string($record[$field]) || strlen($record[$field])>400)) throw new RuntimeException('Invalid field');
            }
            if (in_array($record['kind'],['entrepreneur','unknown'],true)) unset($record['tax_number']);
            $record=array_intersect_key($record,array_flip(['country','kind','name','as_of','registration_number','tax_number','city']));
            if ($query!=='') {
                $found=str_contains(fold($record['name']),$query);
                if ($numeric) {
                    $found=false;
                    foreach (['registration_number','tax_number'] as $key) {
                        $v=$record[$key]??'';
                        if ($v!=='' && ($v===$digits || ($key==='registration_number' && $record['country']==='HR' && strlen($digits)<=9 && ltrim($v,'0')===ltrim($digits,'0')))) $found=true;
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
