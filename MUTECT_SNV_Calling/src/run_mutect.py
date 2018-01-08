from __future__ import print_function

import os
import shlex
import subprocess
from argparse import ArgumentParser

from common_utils.s3_utils import download_file, upload_file, download_folder, upload_folder
from common_utils.job_utils import generate_working_dir, delete_working_dir


def download_reference(s3_path, working_dir):
    """
    Downloads reference folder that has been configured to run with Isaac
    :param s3_path: S3 path that the folder resides in
    :param working_dir: working directory
    :return: local path to the folder containing the reference
    """

    reference_folder = os.path.join(working_dir, 'reference')

    try:
        os.mkdir(reference_folder)
    except Exception as e:
        pass

    download_folder(s3_path, reference_folder)

    # Update sorted reference
    update_sorted_reference(reference_folder)

    return reference_folder


def download_samples_files(bam1_s3_path, bam2_s3_path, working_dir):
    """
    Downlodas the sample files
    :param bam1_s3_path: S3 path containing Tumor BAM 
    :param bam2_s3_path: S3 path containing Normal BAM 
    :param working_dir: working directory
    :return: local path to the folder containing the fastq
    """
    samples_folder = os.path.join(working_dir, 'samples')

    try:
        os.mkdir(samples_folder)
    except Exception as e:
        pass

    local_bam1_path = download_file(bam1_s3_path, samples_folder)
    local_bam2_path = download_file(bam2_s3_path, samples_folder)

    # Isaac requires the fastqs to be symlinked as lane1_read1.fastq.gz and lane1_read2.fastq.gz
    #os.symlink(local_fastq1_path, os.path.join(fastq_folder, 'lane1_read1.fastq.gz'))
    #os.symlink(local_fastq2_path, os.path.join(fastq_folder, 'lane1_read2.fastq.gz'))

    return samples_folder


def upload_bam(vcf_s3_path, local_folder_path):
    """
    Uploads results folder containing the bam file (and associated output)
    :param vcf_s3_path: S3 path to upload the variant calling results to
    :param local_folder_path: local path containing the variant calling results
    """

    upload_folder(vcf_s3_path, local_folder_path)


def run_mutect(gatk_folder_path, reference_dir, samples_folder_path, cmd_args, working_dir):
    """
    Runs Mutect2
	:param gatk_jar: local path to the directory containing the gatk jar
    :param reference_dir: local path to directory containing reference
    :param samples_folder_path: local path to directory containing bam files
    :param cmd_args: additional command-line arguments to pass in
    :param working_dir: working directory
    :return: path to results
    """

    # Maps to GATK's folder structure and change working directory
    os.chdir(working_dir)
    vcf_folder = os.path.join(working_dir, 'Projects/snvs/results')
	
    try:
        os.mkdir(vcf_folder)
    except Exception as e:
        pass
	# This section might cause an error because of the inclusion of reference_folder_path 
    cmd = 'java -jar %s -T MuTect2 -R %s -I:tumor %s -I:normal %s -o %s' % \
          (os.path.join(reference_dir, 'sorted-reference.xml'), gatk_folder_path, reference_folder_path, bam1_s3_path, bam2_s3_path, working_dir, cmd_args)
    print ("Running: %s" % cmd)
    subprocess.check_call(shlex.split(cmd))

    return vcf_folder


def update_sorted_reference(reference_dir):
    """
    Updates sorted-reference.xml to map to the correct directory path. Since each analysis occurs in subfolder of the
    working directory, it will change each execution
    :param reference_dir: Reference directory
    """
    with open(os.path.join(reference_dir, 'sorted-reference.xml'), 'r') as infile:
        sorted_reference = infile.read()

    with open(os.path.join(reference_dir, 'sorted-reference.xml'), 'w') as outfile:
        outfile.write(sorted_reference.replace('/scratch', reference_dir))


def main():
    argparser = ArgumentParser()

    file_path_group = argparser.add_argument_group(title='File paths')
	file_path_group.add_argument('--gatk_s3_path', type=str, help='GATK Jar file', required=True)
	file_path_group.add_argument('--reference_s3_path', type=str, help='reference file', required=True)
	file_path_group.add_argument('--bam1_s3_path', type=str, help='BAM1 s3 path', required=True)
	file_path_group.add_argument('--bam2_s3_path', type=str, help='BAM2 s3  path', required=True)
    

    run_group = argparser.add_argument_group(title='Run command args')
	run_group.add_argument('--cmd_args', type=str, help='Arguments for Mutect', default=' ')
	argparser.add_argument('--working_dir', type=str, default='/scratch')
	args = argparser.parse_args()
	working_dir = generate_working_dir(args.working_dir)

	
	# Download reference files and bam files
    print ('Downloading GATK')
	gatk_folder_path = download_gatk(args.gatk_s3_path, working_dir)
	print ('Downloading Reference')
	reference_folder_path = download_reference(args.reference_s3_path, working_dir)
	print ('Downloading Sample BAMs')
	samples_folder_path = download_samples_files(args.bam1_s3_path, args.bam2_s3_path, working_dir)
	print ('Running Mutect')
	vcf_folder_path = run_mutect(gatk_folder_path, reference_folder_path, bam1_folder_path, bam2_folder_path, args.cmd_args, working_dir)
	
	# Upload results to s3 bucket
	print ('Uploading results to %s' % args.vcf_s3_folder_path)
	upload_vcf(args.vcf_s3_folder_path, vcf_folder_path)
	print('Cleaning up working dir')
	delete_working_dir(working_dir)
	print ('Completed')

if __name__ == '__main__':
    main()