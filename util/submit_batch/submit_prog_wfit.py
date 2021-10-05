# Created Oct 4 2021 by R.Kessler
# Point to directory created by "create_covariance.py"
# and run wfit on hubble_diagram with all covsys_* files
# and with all user-specified WFITOPT options.
 
import os, sys, shutil, yaml, glob
import logging, coloredlogs
import datetime, time
import submit_util as util

from submit_params    import *
from submit_prog_base import Program

PREFIX_wfit   = "wfit"
PREFIX_covsys = "covsys"
HD_FILENAME   = "hubble_diagram.txt"

# column 0 is always for STATE
COLNUM_WFIT_MERGE_DIROPT       = 1
COLNUM_WFIT_MERGE_COVOPT       = 2
COLNUM_WFIT_MERGE_WFITOPT      = 3
COLNUM_WFIT_MERGE_NDOF         = 4   # Ndof

WFITOPT_STRING = "WFITOPT"

JOB_SUFFIX_TAR_LIST  = [ 'YAML', 'DONE', 'LOG'  ]

WFIT_SUMMARY_FILE     = "WFIT_SUMMARY.FITRES"

# - - - - - - - - - - - - - - - - - - -  -
class wFit(Program):
    def __init__(self, config_yaml):

        config_prep = {}
        config_prep['program'] = PROGRAM_NAME_WFIT
        super().__init__(config_yaml, config_prep)

    def set_output_dir_name(self):
        CONFIG     = self.config_yaml['CONFIG']
        input_file = self.config_yaml['args'].input_file  # for msgerr
        msgerr     = []
        if 'OUTDIR' in CONFIG :
            output_dir_name = os.path.expandvars(CONFIG['OUTDIR'])
        else:
            msgerr.append(f"OUTDIR key missing in yaml-CONFIG")
            msgerr.append(f"Check {input_file}")
            log_assert(False,msgerr)

        return output_dir_name,SUBDIR_SCRIPTS_WFIT

    def submit_prepare_driver(self):

        print("")

        # store input directories, and covsys_*
        self.wfit_prep_input_list()

        # store wfit options under WFITOPT key
        self.wfit_prep_wfitopt_list()

        # prepare index list for inpdir/covsys/wfitopt to enable
        # easy 3D loops
        self.wfit_prep_index_lists()

        #sys.exit(f"\n xxx debug exit in submit_prepare_driver \n")
        # end submit_prepare_driver

    def wfit_prep_input_list(self):

        msgerr = []
        input_file      = self.config_yaml['args'].input_file 
        CONFIG          = self.config_yaml['CONFIG']

        key = 'INPDIR_LIST'
        if key not in CONFIG:
            msgerr.append(f"Missing required {key} key in CONFIG block")
            msgerr.append(f"Check {input_file}")
            self.log_assert(False, msgerr)

        wildcard = f"{PREFIX_covsys}*"
        inpdir_list_orig = CONFIG[key]
        inpdir_list   = []
        covsys_list2d = [] # list per inpdir
        for inpdir_orig in inpdir_list_orig:
            inpdir = os.path.expandvars(inpdir_orig)
            inpdir_list.append(inpdir)
            covsys_list  = sorted(glob.glob1(inpdir,wildcard))
            covsys_list2d.append(covsys_list)
            n_covsys = len(covsys_list)
            print(f" Found {n_covsys} {PREFIX_covsys} files under\n" \
                  f"\t {inpdir_orig} ")

        #print(f" xxx covsys_list = {covsys_list} ")
        # - - - - - -
        self.config_prep['inpdir_list_orig']  = inpdir_list_orig
        self.config_prep['inpdir_list']       = inpdir_list
        self.config_prep['n_inpdir']          = len(inpdir_list)
        self.config_prep['covsys_list2d']     = covsys_list2d

        # end wfit_prep_input_list

    def wfit_prep_wfitopt_list(self):

        msgerr = []
        input_file      = self.config_yaml['args'].input_file 
        CONFIG          = self.config_yaml['CONFIG']
        key             = WFITOPT_STRING

        if key not in CONFIG:
            msgerr.append(f"Missing required {key} key in CONFIG block")
            msgerr.append(f"Check {input_file}")
            self.log_assert(False, msgerr)

        wfitopt_rows = CONFIG[key]
        wfitopt_dict = util.prep_jobopt_list(wfitopt_rows, key, None)

        n_wfitopt          = wfitopt_dict['n_jobopt']
        wfitopt_arg_list   = wfitopt_dict['jobopt_arg_list']
        wfitopt_num_list   = wfitopt_dict['jobopt_num_list']
        wfitopt_label_list = wfitopt_dict['jobopt_label_list']
   
        n_wfitopt -= 1
        logging.info(f" Store {n_wfitopt} wfit options from " \
                     f"{key} keys" )

        # exclude 0th element since there is no default
        self.config_prep['n_wfitopt']          = n_wfitopt
        self.config_prep['wfitopt_arg_list']   = wfitopt_arg_list[1:]
        self.config_prep['wfitopt_num_list']   = wfitopt_num_list[1:]
        self.config_prep['wfitopt_label_list'] = wfitopt_label_list[1:]

        # check for global wfitopt
        key   = f"{WFITOPT_STRING}_GLOBAL"
        wfitopt_global = ""
        if key in CONFIG :
            wfitopt_global = CONFIG[key]
        
        self.config_prep['wfitopt_global'] = wfitopt_global

        # end wfit_prep_wfitopt_list

    def wfit_prep_index_lists(self):

        # prepare internal index lists for efficient looping
        CONFIG           = self.config_yaml['CONFIG']
        inpdir_list      = self.config_prep['inpdir_list']  
        covsys_list2d    = self.config_prep['covsys_list2d']
        wfitopt_list     = self.config_prep['wfitopt_arg_list']

        n_inpdir         = self.config_prep['n_inpdir']
        n_wfitopt        = self.config_prep['n_wfitopt']        

        # count total number of jobs, and beware that number
        # of covsys can be different in each inpdir.
        n_job_tot = 0
        idir_list3 = [];  ifit_list3 = [];   icov_list3 = []

        for idir in range(0,n_inpdir):
            covsys_list = covsys_list2d[idir]
            n_covsys    = len(covsys_list)
            for icov in range(0,n_covsys):
                for ifit in range(0,n_wfitopt):
                    n_job_tot += 1
                    idir_list3.append(idir)
                    icov_list3.append(icov)
                    ifit_list3.append(ifit)

        self.config_prep['n_job_split'] = 1
        self.config_prep['n_job_tot']   = n_job_tot
        self.config_prep['n_done_tot']  = n_job_tot

        self.config_prep['idir_list3']  = idir_list3
        self.config_prep['icov_list3']  = icov_list3
        self.config_prep['ifit_list3']  = ifit_list3

        # end wfit_prep_index_lists

    def write_command_file(self, icpu, f):

        input_file      = self.config_yaml['args'].input_file 
        inpdir_list     = self.config_prep['inpdir_list']  
        covsys_list2d   = self.config_prep['covsys_list2d']
        wfitopt_list    = self.config_prep['wfitopt_arg_list']
        n_core          = self.config_prep['n_core']

        idir_list3 = self.config_prep['idir_list3'] 
        icov_list3 = self.config_prep['icov_list3']
        ifit_list3 = self.config_prep['ifit_list3']
        
        n_job_cpu   = 0
        n_job_local = 0

        for idir,icov,ifit in zip(idir_list3,icov_list3,ifit_list3):

            n_job_local += 1
            index_dict = \
                { 'idir':idir, 'ifit':ifit, 'icov':icov, 'icpu':icpu }

            if ( (n_job_local-1) % n_core ) != icpu : continue

            n_job_cpu += 1
            job_info_wfit   = self.prep_JOB_INFO_wfit(index_dict)
            util.write_job_info(f, job_info_wfit, icpu)

            job_info_merge = self.prep_JOB_INFO_merge(icpu,n_job_local) 
            util.write_jobmerge_info(f, job_info_merge, icpu)

        return n_job_cpu

        # end write_command_file

    def prep_JOB_INFO_wfit(self,index_dict):

        idir = index_dict['idir']
        ifit = index_dict['ifit']
        icov = index_dict['icov']

        kill_on_fail = self.config_yaml['args'].kill_on_fail
        program      = self.config_prep['program']
        output_dir   = self.config_prep['output_dir']
        script_dir   = self.config_prep['script_dir']

        inpdir      = self.config_prep['inpdir_list_orig'][idir]
        arg_string  = self.config_prep['wfitopt_arg_list'][ifit]
        arg_global  = self.config_prep['wfitopt_global']
        covsys_file = self.config_prep['covsys_list2d'][idir][icov]

        prefix = self.wfit_num_string(idir,icov,ifit)

        hd_file    = f"{inpdir}/{HD_FILENAME}"
        log_file   = f"{prefix}.LOG" 
        done_file  = f"{prefix}.DONE"
        all_done_file = f"{output_dir}/{DEFAULT_DONE_FILE}"

        arg_list =  [ arg_string ]
        if len(arg_global) > 0: arg_list.append(arg_global)
        arg_list.append(f"-cospar_yaml {prefix}.YAML")

        JOB_INFO = {}
        JOB_INFO['program']       = program
        JOB_INFO['input_file']    = hd_file
        JOB_INFO['job_dir']       = script_dir
        JOB_INFO['log_file']      = f"{log_file}"
        JOB_INFO['done_file']     = f"{done_file}"
        JOB_INFO['all_done_file'] = f"{all_done_file}"
        JOB_INFO['kill_on_fail']  = kill_on_fail
        JOB_INFO['arg_list']      = arg_list
  
        return JOB_INFO

        # end prep_JOB_INFO_wfit

    def wfit_num_string(self,idir,icov,ifit):

        if idir >= 0 and icov < 0 and ifit < 0:
            string = f"DIROPT{idir:03d}"

        elif icov >= 0 and idir < 0 and ifit < 0 :
            string = f"COVOPT{icov:03d}"

        elif ifit >= 0 and idir < 0 and icov < 0 :
            string = f"WFITOPT{ifit:03d}"

        elif idir < 0 and ifit>=0 and icov>=0 :
            string = f"COVOPT{icov:03d}_WFITOPT{ifit:03d}"

        elif idir >= 0 and ifit>=0 and icov>=0 :
            string = f"DIROPT{idir:03d}_COVOPT{icov:03d}_WFITOPT{ifit:03d}"
        else:
            string = "ERROR"

        return string
        # end wfit_num_string

    def wfit_prefix(self,row):
        # parse input row passed from MERGE.LOG and construct
        # prefix for output files
        dirnum  = row[COLNUM_WFIT_MERGE_DIROPT]
        covnum  = row[COLNUM_WFIT_MERGE_COVOPT]
        wfitnum = row[COLNUM_WFIT_MERGE_WFITOPT]
        prefix = f"{dirnum}_{covnum}_{wfitnum}"
        return prefix

        # end wfit_prefix

    def append_info_file(self,f):
        # append info to SUBMIT.INFO file

        n_wfitopt     = self.config_prep['n_wfitopt']

        f.write(f"\n# wfit info\n")

        f.write(f"JOBFILE_WILDCARD:  'DIR*COVOPT*WFITOPT*' \n")

        f.write(f"N_WFITOPT:         {n_wfitopt}      " \
                f"# number of wfit options\n")

        # end append_info_file  

    def create_merge_table(self,f):

        # create merge table with NDOF=0; later this table
        # gets updated as jobs finish.
        idir_list3      = self.config_prep['idir_list3']
        icov_list3      = self.config_prep['icov_list3'] 
        ifit_list3      = self.config_prep['ifit_list3']
        
        # create only MERGE table ... no need for SPLIT table
        header_line_merge = \
            (f" STATE  DIROPT  COVOPT  WFITOPT  NDOF" \
             f" SPLITRAN" )

        INFO_MERGE = { 
            'primary_key' : TABLE_MERGE, 'header_line' : header_line_merge,
            'row_list'    : []   }

        STATE = SUBMIT_STATE_WAIT # all start in WAIT state

        for idir,icov,ifit in \
            zip(idir_list3,icov_list3,ifit_list3):

            diropt_num  = self.wfit_num_string(idir,-1,-1)
            covopt_num  = self.wfit_num_string(-1,icov,-1)
            wfitopt_num = self.wfit_num_string(-1,-1,ifit)

            # ROW here is fragile in case columns are changed
            ROW_MERGE = []
            ROW_MERGE.append(STATE)
            ROW_MERGE.append(diropt_num)
            ROW_MERGE.append(covopt_num)
            ROW_MERGE.append(wfitopt_num)
            ROW_MERGE.append(0)
            ROW_MERGE.append(None)
            INFO_MERGE['row_list'].append(ROW_MERGE)  

        # - - - - -
        util.write_merge_file(f, INFO_MERGE, [] ) 
            
        # end create_merge_file

    def merge_config_prep(self,output_dir):
        submit_info_yaml = self.config_prep['submit_info_yaml']
        
    def merge_update_state(self, MERGE_INFO_CONTENTS):

        # read MERGE.LOG, check LOG & DONE files.
        # Return update row list MERGE tables.

        submit_info_yaml = self.config_prep['submit_info_yaml']
        output_dir       = self.config_prep['output_dir']
        script_dir       = submit_info_yaml['SCRIPT_DIR']
        n_job_split      = submit_info_yaml['N_JOB_SPLIT']

        COLNUM_STATE     = COLNUM_MERGE_STATE
        COLNUM_DIROPT    = COLNUM_WFIT_MERGE_DIROPT
        COLNUM_COVOPT    = COLNUM_WFIT_MERGE_COVOPT  
        COLNUM_WFITOPT   = COLNUM_WFIT_MERGE_WFITOPT  
        COLNUM_NDOF      = COLNUM_WFIT_MERGE_NDOF
        NROW_DUMP   = 0

        key_ndof, key_ndof_sum, key_ndof_list = \
                self.keynames_for_job_stats('Ndof')
        key_list = [ key_ndof ] 

        row_list_merge   = MERGE_INFO_CONTENTS[TABLE_MERGE]

        # init outputs of function
        n_state_change     = 0
        row_list_merge_new = []

        nrow_check = 0
        for row in row_list_merge :
            row_list_merge_new.append(row) # default output is same as input
            nrow_check += 1
            irow        = nrow_check - 1 # row index

           # strip off row info
            STATE       = row[COLNUM_STATE]
            prefix      = self.wfit_prefix(row) 
            search_wildcard = f"{prefix}*"

            # check if DONE or FAIL ; i.e., if Finished
            Finished = (STATE == SUBMIT_STATE_DONE) or \
                       (STATE == SUBMIT_STATE_FAIL)

            if not Finished :
                NEW_STATE = STATE

                # get list of LOG, DONE, and YAML files 
                log_list, done_list, yaml_list = \
                    util.get_file_lists_wildcard(script_dir,search_wildcard)

                # careful to sum only the files that are NOT None
                NLOG   = sum(x is not None for x in log_list)  
                NDONE  = sum(x is not None for x in done_list)  
                NYAML  = sum(x is not None for x in yaml_list)  

                if NLOG > 0:
                    NEW_STATE = SUBMIT_STATE_RUN
                if NDONE == n_job_split :
                    NEW_STATE = SUBMIT_STATE_DONE
                    
                    wfit_stats = self.get_job_stats(script_dir,
                                                    log_list, 
                                                    yaml_list, 
                                                    key_list)
                    
                    # check for failures in snlc_fit jobs.
                    nfail = wfit_stats['nfail']
                    if nfail > 0 :  NEW_STATE = SUBMIT_STATE_FAIL
                 
                    row[COLNUM_STATE]     = NEW_STATE
                    row[COLNUM_NDOF]      = wfit_stats[key_ndof_sum]
                    
                    row_list_merge_new[irow] = row  # update new row
                    n_state_change += 1             # assume nevt changes

        # - - - - - -  -
        # The first return arg (row_split) is null since there is 
        # no need for a SPLIT table
        return [], row_list_merge_new, n_state_change

        # end merge_update_state

    def merge_job_wrapup(self, irow, MERGE_INFO_CONTENTS):
        submit_info_yaml = self.config_prep['submit_info_yaml']
        output_dir       = self.config_prep['output_dir']
        script_dir       = submit_info_yaml['SCRIPT_DIR']
        row     = MERGE_INFO_CONTENTS[TABLE_MERGE][irow]

        # end merge_job_wrapup

    def merge_cleanup_final(self):
        output_dir       = self.config_prep['output_dir']
        submit_info_yaml = self.config_prep['submit_info_yaml']
        script_dir       = submit_info_yaml['SCRIPT_DIR']
        jobfile_wildcard = submit_info_yaml['JOBFILE_WILDCARD']
        script_subdir    = SUBDIR_SCRIPTS_WFIT

        self.make_wfit_summary()

        logging.info(f"  wfit cleanup: compress {JOB_SUFFIX_TAR_LIST}")
        for suffix in JOB_SUFFIX_TAR_LIST :
            wildcard = (f"{jobfile_wildcard}*.{suffix}") 
            util.compress_files(+1, script_dir, wildcard, suffix, "" )

        logging.info("")

        self.merge_cleanup_script_dir()

        # end merge_cleanup_final

    def make_wfit_summary(self):

        output_dir       = self.config_prep['output_dir']
        submit_info_yaml = self.config_prep['submit_info_yaml']
        script_dir       = submit_info_yaml['SCRIPT_DIR']

        SUMMARYF_FILE     = (f"{output_dir}/{WFIT_SUMMARY_FILE}")
        f = open(SUMMARYF_FILE,"w") 

        # check w0,wa or w; could be different for each case ?
        VARNAMES_STRING = \
            "ROW  DIROPT COVOPT WFITOPT  w0 w0sig wa wa_sig "  \
            "omm omm_sig  chi2 sigint"

        MERGE_LOG_PATHFILE  = (f"{output_dir}/{MERGE_LOG_FILE}")
        MERGE_INFO_CONTENTS,comment_lines = \
                util.read_merge_file(MERGE_LOG_PATHFILE)

        nrow = 0 
        for row in MERGE_INFO_CONTENTS[TABLE_MERGE]:
            nrow += 1
            prefix     = self.wfit_prefix(row)
            YAML_FILE  = (f"{script_dir}/{prefix}.YAML")
            wfit_yaml  = util.extract_yaml(YAML_FILE, None, None )
            
 
        f.close()
        # .xyz
        # end make_wfit_summary

    def get_misc_merge_info(self):
        # return misc info lines to write into MERGE.LOG file  
        submit_info_yaml = self.config_prep['submit_info_yaml']
        info_lines = []
        return info_lines
        # end get_misc_merge_info 

    def get_merge_COLNUM_CPU(self):
        return -9  # there is no CPU column

    # === END: ===