"""One-time owner enrollment: private repository and local OS credential store."""
import argparse
import getpass
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from native_vault import NativeVault, VaultUnavailable
from registry import RegistryAccess
from tools.live_registry_check import check


def gh_call(args, payload=None):
    executable=shutil.which('gh')
    if not executable:
        raise ValueError('Install GitHub CLI first.')
    result=subprocess.run([executable,*args],input=payload,capture_output=True,timeout=60,check=False)  # nosec B603 -- fixed CLI, secret via stdin only
    if result.returncode:
        raise ValueError('GitHub CLI authorization or configuration failed.')
    return result.stdout


def publish_secrets(pair,repository='bren-wp/Crawlvore'):
    info=json.loads(gh_call(['repo','view',repository,'--json','visibility']))
    if info.get('visibility')!='PRIVATE':
        raise ValueError('Repository must be private before enrollment.')
    # The owner creates the production-api environment; never reset its protection rules.
    gh_call(['api','repos/'+repository+'/environments/production-api','--jq','.name'])
    names=('SUDREG_CLIENT_ID','SUDREG_CLIENT_SECRET')
    for name,value in zip(names,pair):
        gh_call(['secret','set',name,'--repo',repository,'--env','production-api'],value.encode())
    saved=json.loads(gh_call(['secret','list','--repo',repository,'--env','production-api','--json','name']))
    if not set(names)<={item['name'] for item in saved}:
        raise ValueError('GitHub secret name verification failed.')
    print('Both private GitHub environment secrets configured and names verified.')


def enroll(workspace,reuse=False):
    vault=NativeVault(workspace,purpose='registry')
    if reuse:
        record=vault.load()
        if not record or record.get('authorized') is not True:
            raise ValueError('Authorized local vault record required.')
        pair=RegistryAccess._pair(record)
    else:
        if not sys.stdin.isatty():
            raise ValueError('Interactive terminal required for hidden credential entry.')
        pair=RegistryAccess._pair({'client_id':getpass.getpass('Authorized Client ID: '),
                                   'client_secret':getpass.getpass('Authorized Client Secret: ')})
    check(pair)
    if not reuse:
        access=RegistryAccess(Path(__file__).resolve().parents[1],workspace)
        access.apply({'client_id':pair[0],'client_secret':pair[1],'persist':True,'permission':True})
    record=vault.load()
    if not record or record.get('authorized') is not True or RegistryAccess._pair(record)!=pair:
        raise ValueError('Local secure enrollment could not be verified.')
    print('Local operating-system vault configured and verified.')
    return pair


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('workspace',type=Path)
    parser.add_argument('--github',action='store_true',help='Also enroll environment Actions secrets; repository must be private.')
    parser.add_argument('--reuse-vault',action='store_true',help='Use existing authorized local vault without prompting.')
    args=parser.parse_args()
    # Local enrollment must succeed even when GitHub login is unavailable.
    pair=enroll(args.workspace.resolve(),args.reuse_vault)
    if args.github:
        publish_secrets(pair)


if __name__=='__main__':
    try:
        main()
    except (ValueError,VaultUnavailable,OSError,subprocess.TimeoutExpired,KeyError,TypeError) as error:
        print('Enrollment incomplete: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(1) from None
