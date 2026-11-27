<?php
declare(strict_types=1);
$base=sys_get_temp_dir().'/cv-wp-test-'.bin2hex(random_bytes(8));
mkdir($base,0700);mkdir($base.'/public');mkdir($base.'/catalog');mkdir($base.'/catalog/HR');mkdir($base.'/catalog/GB');
define('ABSPATH',$base.'/public/');
$_SERVER['DOCUMENT_ROOT']=$base.'/public';
require __DIR__.'/../wordpress/crawlvora-business-directory/includes/class-catalog.php';
use Crawlvora\Directory\Catalog;
function check(bool $ok,string $message):void {if(!$ok)throw new RuntimeException($message);}
function fixture(string $root,string $country,string $kind,array $rows):void {
    $name=$country.'-'.$kind.'-000001.json';
    file_put_contents($root.'/'.$country.'/'.$name,json_encode($rows,JSON_THROW_ON_ERROR));
    file_put_contents($root.'/'.$country.'/manifest.json',json_encode(['country'=>$country,'count'=>count($rows),'shards'=>[$name]],JSON_THROW_ON_ERROR));
}
function clean(string $path):void {
    if(is_link($path)||is_file($path)){unlink($path);return;}
    foreach(new FilesystemIterator($path) as $item)clean($item->getPathname());
    rmdir($path);
}
try {
    $root=$base.'/catalog';
    check(Catalog::private_root($root)!==null,'private path rejected');
    check(Catalog::private_root($base)===null,'public ancestor allowed');
    check(Catalog::private_root(ABSPATH)===null,'public path allowed');
    $hr=['name'=>'Čakovec','country'=>'HR','kind'=>'entrepreneur','as_of'=>'2026-01-01','registration_number'=>'000000123','tax_number'=>'12345678901','email'=>'private@example.test'];
    fixture($root,'HR','entrepreneur',array_fill(0,26,$hr));
    fixture($root,'GB','company',[['name'=>'Synthetic British Ltd','country'=>'GB','kind'=>'company','as_of'=>'2026-01-01','registration_number'=>'AB123456']]);
    $found=Catalog::search($root,'HR','','123',1);
    check(count($found['rows'])===25 && $found['next'],'pagination');
    check(count(Catalog::search($root,'HR','','čakovec',2)['rows'])===1,'case and second page');
    check($found['rows'][0]['tax_number']===''&&!isset($found['rows'][0]['email']),'minimization');
    check(Catalog::search($root,'HR','company','',1)['rows']===[],'classification');
    check(Catalog::search($root,'GB','','ab123456',1)['rows'][0]['name']==='Synthetic British Ltd','GB lookup');
    check(Catalog::search($root,'HR','','AB123456',1)['rows']===[],'country separation');
    check(Catalog::profile($root,'GB','company','AB123456')['name']==='Synthetic British Ltd','exact profile');
    check(Catalog::profile($root,'GB','company','AB123')===null,'partial profile');
    check(Catalog::profile($root,'HR','entrepreneur','000000123')===null,'ambiguous profile');
    check(Catalog::profile($root,'GB','company','../secret')===null,'invalid profile identifier');
    file_put_contents($root.'/HR/manifest.json','{"country":"HR","count":1,"shards":["../../public/secret.json"]}');
    try{Catalog::search($root,'HR','','',1);throw new LogicException('traversal allowed');}catch(RuntimeException $e){check($e->getMessage()==='Invalid shard.','wrong rejection');}
    echo "WORDPRESS_CATALOG_TEST_PASS\n";
}finally{clean($base);}
