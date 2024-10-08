#!/usr/bin/env python

"""
Script that imports locally stored data as a new dataset for the user
Usage: import id outputfile
"""
import sys, os
from shutil import copyfile

assert sys.version_info[:2] >= ( 2, 4 )

BUFFER = 1048576

uids = sys.argv[1].split(",")
out_file1 = sys.argv[2]

#remove NONE from uids
have_none = True
while have_none:
    try:
        uids.remove('None')
    except:
        have_none = False


#create dictionary keyed by uid of tuples of (displayName,filePath,build) for all files
available_files = {}
try:
    filename = sys.argv[-1]
    for i, line in enumerate( file( filename ) ):
        if not line or line[0:1] == "#" : continue
        fields = line.split('\t')
        try:
            info_type = fields.pop(0)
            
            if info_type.upper()=="DATA":
                uid = fields.pop(0)
                org_num = fields.pop(0)
                chr_acc = fields.pop(0)
                feature = fields.pop(0)
                filetype = fields.pop(0)
                path = fields.pop(0).replace("\r","").replace("\n","")
                
                file_type = filetype
                build = org_num
                description = uid
            else:
                continue
        except:
            continue

        available_files[uid]=(description,path,build,file_type,chr_acc)
except:
    print >>sys.stderr, "It appears that the configuration file for this agent is missing."

#create list of tuples of (displayName,FileName,build) for desired files
desired_files = []
for uid in uids:
    try:
        desired_files.append(available_files[uid])
    except:
        continue

#copy first file to contents of given output file
file1_copied = False
while not file1_copied:
    try:
        first_file = desired_files.pop(0)
    except:
        print >>sys.stderr, "There were no valid files requested."
        sys.exit()
    file1_desc, file1_path, file1_build, file1_type,file1_chr_acc = first_file
    try:
        copyfile(file1_path,out_file1)
        print "#File1\t"+file1_desc+"\t"+file1_chr_acc+"\t"+file1_build+"\t"+file1_type
        file1_copied = True
    except:
        print >>sys.stderr, "The file specified is missing."
        continue
        #print >>sys.stderr, "The file specified is missing."
    

#Tell post-process filter where remaining files reside
for extra_output in desired_files:
    file_desc, file_path, file_build, file_type,file_chr_acc = extra_output
    print "#NewFile\t"+file_desc+"\t"+file_chr_acc+"\t"+file_build+"\t"+file_path+"\t"+file_type
