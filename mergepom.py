#! /usr/bin/env python

# Copyright 2013 Ralf Thielow <ralf.thielow@gmail.com>
# Licensed under the GNU GPL version 2.

import codecs
import re
import shlex
import subprocess
import sys
import xml.dom.minidom as dom

def get_enc(line, default):
    m = re.search('encoding=[\'"](.*?)[\'"]', line)
    if m is not None:
        return m.group(1)
    return default


def change_version(old_version, new_version, cont):
    return cont.replace("<commonAppVersion>" + old_version + "</commonAppVersion>",
                        "<commonAppVersion>" + new_version + "</commonAppVersion>")


def check_output(*popenargs, **kwargs):
    r"""Run command with arguments and return its output as a byte string.
    Backported from Python 2.7 as it's implemented as pure python on stdlib.
    >>> check_output(['/usr/bin/python', '--version'])
    Python 2.6.2
    """
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        error = subprocess.CalledProcessError(retcode, cmd)
        error.output = output
        raise error
    return output

def get_project_version(f):
    try:
        tree = dom.parse(f)
        version = None
        parent_version = None
        for entry in tree.documentElement.childNodes:
            if entry.nodeName == "properties":
                for entry2 in entry.childNodes:
                    if entry2.nodeName == 'commonAppVersion':
                        version = entry2.firstChild.data

        if version is not None:
            # version has a priority over parent version
            return version
        else:
            # may return None
            return parent_version
    except:
        print(sys.argv[0] + ': error while parsing pom.xml')
        return None


sys.stdout = open('/home/developer/env/mergepom_stdout.log', 'w')
sys.stderr = open('/home/developer/env/mergepom_stderr.log', 'w')


if len(sys.argv) == 2:
    current_branch_version = get_project_version(sys.argv[1])
    print(current_branch_version)

if len(sys.argv) < 4 or len(sys.argv) > 5:
    print("Wrong number of arguments.")
    sys.exit(-1)

ancestor_version = get_project_version(sys.argv[1])
current_branch_version = get_project_version(sys.argv[2])
other_branch_version = get_project_version(sys.argv[3])


# change current version in order to avoid merge conflicts
if (
    current_branch_version is not None
    and other_branch_version is not None
    and ancestor_version is not None
    and current_branch_version != other_branch_version
    and other_branch_version != ancestor_version
):
    with open(sys.argv[2], 'r') as f:
        enc = get_enc(f.readline(), 'utf-8')
    with codecs.open(sys.argv[2], 'r', enc) as f:
        other = f.read()
    other = change_version(current_branch_version, other_branch_version, other)
    with codecs.open(sys.argv[2], 'w', enc) as f:
        f.write(other)

cmd = "git merge-file -p -L mine -L base -L theirs " + sys.argv[2] + " " + sys.argv[1] + " " + sys.argv[3]
p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
git_merge_res = p.communicate()[0]
ret = p.returncode

enc = 'utf-8'
try:
    git_merge_res_str = git_merge_res.decode(enc)
except:
    # utf-8 failed, try again with iso-8859-1
    enc = 'iso-8859-1'
    git_merge_res_str = git_merge_res.decode(enc)

oenc = get_enc(git_merge_res_str.splitlines()[0], enc)
if enc != oenc:
    enc = oenc
    git_merge_res_str = git_merge_res.decode(enc)

cmd = "git rev-parse --abbrev-ref HEAD"
p = check_output(shlex.split(cmd))
branch = p.strip().decode('utf-8')

cmd = "git config --get --bool merge.pommerge.keepmasterversion"
p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
val = p.communicate()[0]
val = val.strip().decode('utf-8')

keep = False
if (p.returncode == 0 and val == 'true'):
    keep = True

# revert pom project version on current branch, unless in master. Allows for gitflow release-finish, hotfix-finish, and feature-finish to work better
if (current_branch_version is not None and (keep or branch != 'master')):
    print('Merging pom version ' + other_branch_version + ' into ' + branch + '. Keeping version ' + current_branch_version)
    git_merge_res_str = change_version(other_branch_version, current_branch_version, git_merge_res_str)

with codecs.open(sys.argv[2], 'w', enc) as f:
    f.write(git_merge_res_str)

sys.exit(ret)
