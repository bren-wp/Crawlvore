"""Recover on a replacement computer using manifest, archive and independent passphrase."""
import argparse
import getpass
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from portable_recovery import recover

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('archive',type=Path)
    parser.add_argument('new_workspace',type=Path)
    parser.add_argument('--expected-head',help='Latest catalog head obtained independently from the backup set')
    args=parser.parse_args()
    try:
        result=recover(args.manifest,args.archive,args.new_workspace,getpass.getpass('Recovery passphrase: '),args.expected_head)
    except Exception as error:
        parser.exit(1,'Recovery failed; original files preserved. '+type(error).__name__+'\n')
    print('Verified recovered workspace:',result.parent)
