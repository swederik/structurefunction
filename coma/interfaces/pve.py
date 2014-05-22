from nipype.interfaces.matlab import MatlabCommand
from nipype.interfaces.base import (
    BaseInterface, BaseInterfaceInputSpec, traits, InputMultiPath,
    OutputMultiPath, File, TraitedSpec, Directory, isdefined)
from nipype.utils.filemanip import split_filename
import os
import os.path as op
from string import Template
import nibabel as nb
import glob
import logging
import numpy as np
import random
import gzip
import shutil
logging.basicConfig()
iflogger = logging.getLogger('interface')


def nifti_to_analyze(nii):
    nifti = nb.load(nii)
    if nii[-3:] == '.gz':
        nif = gzip.open(nii, 'rb')
    else:
        nif = open(nii, 'rb')
    hdr = nb.nifti1.Nifti1Header.from_fileobj(nif)

    arr_hdr = nb.analyze.AnalyzeHeader.from_header(hdr)
    arrb = hdr.raw_data_from_fileobj(nif)
    img = nb.AnalyzeImage(
        dataobj=arrb, affine=nifti.get_affine(), header=arr_hdr)
    _, name, _ = split_filename(nii)
    nb.analyze.save(img, op.abspath(name + '.img'))
    return op.abspath(name + '.img'), op.abspath(name + '.hdr')


def analyze_to_nifti(img, ext='.nii.gz', affine=None):
    image = nb.load(img)
    _, name, _ = split_filename(img)
    if affine is None:
        nii = nb.Nifti1Image.from_image(image)
        affine = image.get_affine()
        nii.set_sform(affine)
        nii.set_qform(affine)
    else:
        nii = nb.Nifti1Image(dataobj=image.get_data(),
            header=image.get_header(), affine=affine)

    nb.save(nii, op.abspath(name + ext))
    return op.abspath(name + ext)


def fix_roi_values(roi_image, white_matter_file, csf_file):
    '''
    Changes ROI values to prevent values equal to 1, 2,
    or 3. These are reserved for GM/WM/CSF in the PVELab
    functions.
    '''

    image = nb.load(roi_image)
    data = image.get_data()
    data = data.astype(np.uint8)
    data[data > 0] = data[data > 0] + 50

    wm_image = nb.load(white_matter_file)
    wm_data = wm_image.get_data()
    csf_image = nb.load(csf_file)
    csf_data = csf_image.get_data()

    assert (data.shape == wm_data.shape == csf_data.shape)
    data[(wm_data > 0)*(data == 0)] = 2
    data[(csf_data > 0)*(data == 0)] = 3

    hdr = image.get_header()
    fixed = nb.Nifti1Image(
        dataobj=data, affine=image.get_affine(), header=hdr)
    _, name, _ = split_filename(roi_image)
    fixed.set_data_dtype(np.uint8)
    fixed_roi_image = op.abspath(name + "_p100.nii.gz")
    nb.save(fixed, fixed_roi_image)
    return fixed_roi_image

def switch_datatype(in_file, dt=np.uint8):
    '''
    Changes ROI values to prevent values equal to 1, 2,
    or 3. These are reserved for GM/WM/CSF in the PVELab
    functions.
    '''

    image = nb.load(in_file)
    image.set_data_dtype(dt)
    _, name, _ = split_filename(in_file)
    fixed_image = op.abspath(name + "_u8.nii.gz")
    nb.save(image, fixed_image)
    return fixed_image

def write_config_dat(roi_file, use_fs_LUT=False):
    out_file = "ROI_names.dat"
    f = open(out_file, "w")
    f.write(
        "Report ROI coding #, ROI Name and color in hexaddecimal, separated by a <Tab> hereinafter, with no space at the end\n")
    image = nb.load(roi_file)
    data = image.get_data()
    IDs = np.unique(data)
    IDs.sort()
    IDs = IDs.tolist()
    if 0 in IDs:
        IDs.remove(0)
    if 1 in IDs:
        IDs.remove(1)
    if 2 in IDs:
        IDs.remove(2)
    if 3 in IDs:
        IDs.remove(3)
    r = lambda: random.randint(0, 255)
    for idx, val in enumerate(IDs):
        # e.g. 81  R_Hippocampus       008000
        f.write("%i\tRegion%i\t%02X%02X%02X\n" % (val, idx, r(), r(), r()))
    f.close()
    return op.abspath(out_file)


class PartialVolumeCorrectionInputSpec(BaseInterfaceInputSpec):
    pet_file = File(exists=True, mandatory=True,
                    desc='The input PET image')
    t1_file = File(exists=True, mandatory=True,
                   desc='The input T1')
    white_matter_file = File(exists=True,
                             desc='Segmented white matter')
    grey_matter_file = File(exists=True,
                            desc='Segmented grey matter')
    csf_file = File(exists=True,
                    desc='Segmented cerebrospinal fluid')
    roi_file = File(exists=True, mandatory=True, xor=['skip_atlas'],
                    desc='The input ROI image')
    skip_atlas = traits.Bool(xor=['roi_file'],
                             desc='Uses the WM/GM/CSF segmentation instead of an atlas')
    use_fs_LUT = traits.Bool(True, usedefault=True,
                             desc='Uses the Freesurfer lookup table for names in the atlas')


class PartialVolumeCorrectionOutputSpec(TraitedSpec):
    alfano_alfano = File(
        exists=True, desc='alfano_alfano')
    alfano_cs = File(
        exists=True, desc='alfano_cs')
    alfano_rousset = File(
        exists=True, desc='alfano_rousset')
    mueller_gartner_alfano = File(
        exists=True, desc='mueller_gartner_alfano')
    mask = File(
        exists=True, desc='mask')
    occu_mueller_gartner = File(
        exists=True, desc='occu_mueller_gartner')
    occu_meltzer = File(
        exists=True, desc='occu_meltzer')
    meltzer = File(
        exists=True, desc='meltzer')
    mueller_gartner_rousset = File(
        exists=True, desc='mueller_gartner_rousset')
    mueller_gartner_WMroi = File(
        exists=True, desc='mueller_gartner_WMroi')
    virtual_pet_image = File(
        exists=True, desc='virtual_pet_image')
    white_matter_roi = File(
        exists=True, desc='white_matter_roi')
    rousset_mat_file = File(
        exists=True, desc='rousset_mat_file')
    point_spread_image = File(
        exists=True, desc='point_spread_image')
    out_files = OutputMultiPath(File,
        exists=True, desc='all PVE files')

class PartialVolumeCorrection(BaseInterface):

    """
    Wraps PVELab for partial volume correction

    PVE correction includes Meltzer, M\"{u}eller-Gartner, Rousset and
    modified M\"{u}eller-Gartner (WM value estimated using Rousset method)
    approaches.

    """
    input_spec = PartialVolumeCorrectionInputSpec
    output_spec = PartialVolumeCorrectionOutputSpec

    def _run_interface(self, runtime):
        list_path = op.abspath("SubjectList.lst")
        pet_path, _ = nifti_to_analyze(self.inputs.pet_file)
        t1_path, _ = nifti_to_analyze(self.inputs.t1_file)
        f = open(list_path, 'w')
        f.write("%s;%s" % (pet_path, t1_path))
        f.close()
        
        orig_t1 = nb.load(self.inputs.t1_file)
        orig_affine = orig_t1.get_affine()

        gm_uint8 = switch_datatype(self.inputs.grey_matter_file)
        gm_path, _ = nifti_to_analyze(gm_uint8)
        iflogger.info("Writing to %s" % gm_path)

        wm_uint8 = switch_datatype(self.inputs.white_matter_file)
        wm_path, _ = nifti_to_analyze(wm_uint8)
        iflogger.info("Writing to %s" % wm_path)

        csf_uint8 = switch_datatype(self.inputs.csf_file)
        csf_path, _ = nifti_to_analyze(csf_uint8)
        iflogger.info("Writing to %s" % csf_path)

        fixed_roi_file = fix_roi_values(self.inputs.roi_file, self.inputs.white_matter_file, self.inputs.csf_file)
        rois_path, _ = nifti_to_analyze(fixed_roi_file)
        iflogger.info("Writing to %s" % rois_path)

        dat_path = write_config_dat(
            fixed_roi_file, self.inputs.use_fs_LUT)
        iflogger.info("Writing to %s" % dat_path)

        d = dict(
            list_path=list_path,
            gm_path=gm_path,
            wm_path=wm_path,
            csf_path=csf_path,
            rois_path=rois_path,
            dat_path=dat_path)
        script = Template("""       
        filelist = '$list_path';
        gm = '$gm_path';
        wm = '$wm_path';
        csf = '$csf_path';
        rois = '$rois_path';
        dat = '$dat_path';
        runbatch_nogui(filelist, gm, wm, csf, rois, dat)
        """).substitute(d)
        mlab = MatlabCommand(script=script, mfile=True,
                             prescript=[''], postscript=[''])
        result = mlab.run()

        _, foldername, _ = split_filename(self.inputs.pet_file)
        occu_MG_img = glob.glob("pve_%s/r_volume_Occu_MG.img" % foldername)[0] 
        analyze_to_nifti(occu_MG_img, affine=orig_affine)
        occu_meltzer_img = glob.glob("pve_%s/r_volume_Occu_Meltzer.img" % foldername)[0] 
        analyze_to_nifti(occu_meltzer_img, affine=orig_affine)
        meltzer_img = glob.glob("pve_%s/r_volume_Meltzer.img" % foldername)[0] 
        analyze_to_nifti(meltzer_img, affine=orig_affine)
        MG_rousset_img = glob.glob("pve_%s/r_volume_MGRousset.img" % foldername)[0] 
        analyze_to_nifti(MG_rousset_img, affine=orig_affine)
        MGCS_img = glob.glob("pve_%s/r_volume_MGCS.img" % foldername)[0] 
        analyze_to_nifti(MGCS_img, affine=orig_affine)
        virtual_PET_img = glob.glob("pve_%s/r_volume_Virtual_PET.img" % foldername)[0] 
        analyze_to_nifti(virtual_PET_img, affine=orig_affine)
        centrum_semiovalue_WM_img = glob.glob("pve_%s/r_volume_CSWMROI.img" % foldername)[0] 
        analyze_to_nifti(centrum_semiovalue_WM_img, affine=orig_affine)
        alfano_alfano_img = glob.glob("pve_%s/r_volume_AlfanoAlfano.img" % foldername)[0] 
        analyze_to_nifti(alfano_alfano_img, affine=orig_affine)
        alfano_cs_img = glob.glob("pve_%s/r_volume_AlfanoCS.img" % foldername)[0] 
        analyze_to_nifti(alfano_cs_img, affine=orig_affine)
        alfano_rousset_img = glob.glob("pve_%s/r_volume_AlfanoRousset.img" % foldername)[0] 
        analyze_to_nifti(alfano_rousset_img, affine=orig_affine)
        mg_alfano_img = glob.glob("pve_%s/r_volume_MGAlfano.img" % foldername)[0] 
        analyze_to_nifti(mg_alfano_img, affine=orig_affine)
        mask_img = glob.glob("pve_%s/r_volume_Mask.img" % foldername)[0] 
        analyze_to_nifti(mask_img, affine=orig_affine)
        PSF_img = glob.glob("pve_%s/r_volume_PSF.img" % foldername)[0] 
        analyze_to_nifti(PSF_img)

        rousset_mat_file = glob.glob("pve_%s/r_volume_Rousset.mat" % foldername)[0]
        shutil.copyfile(rousset_mat_file, op.abspath("r_volume_Rousset.mat"))
        return result.runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs['occu_mueller_gartner'] = op.abspath("r_volume_Occu_MG.nii.gz")
        outputs['occu_meltzer'] = op.abspath("r_volume_Occu_Meltzer.nii.gz")
        outputs['meltzer'] = op.abspath("r_volume_Meltzer.nii.gz")
        outputs['mueller_gartner_rousset'] = op.abspath(
            "r_volume_MGRousset.nii.gz")
        outputs['mueller_gartner_WMroi'] = op.abspath("r_volume_MGCS.nii.gz")
        outputs['virtual_pet_image'] = op.abspath(
            "r_volume_Virtual_PET.nii.gz")
        outputs['white_matter_roi'] = op.abspath("r_volume_CSWMROI.nii.gz")
        outputs['rousset_mat_file'] = op.abspath("r_volume_Rousset.mat")
        outputs['point_spread_image'] = op.abspath("r_volume_PSF.nii.gz")
        outputs['mask'] = op.abspath("r_volume_Mask.nii.gz")
        outputs['alfano_alfano'] = op.abspath("r_volume_AlfanoAlfano.nii.gz")
        outputs['alfano_cs'] = op.abspath("r_volume_AlfanoCS.nii.gz")
        outputs['alfano_rousset'] = op.abspath("r_volume_AlfanoRousset.nii.gz")
        outputs['mueller_gartner_alfano'] = op.abspath(
            "r_volume_MGAlfano.nii.gz")
        outputs['out_files'] = [outputs['occu_mueller_gartner'],
                                outputs['occu_meltzer'],
                                outputs['meltzer'],
                                outputs['mueller_gartner_rousset'],
                                outputs['mueller_gartner_WMroi'],
                                outputs['virtual_pet_image'],
                                outputs['white_matter_roi'],
                                outputs['rousset_mat_file'],
                                outputs['alfano_alfano'],
                                outputs['alfano_cs'],
                                outputs['alfano_rousset'],
                                outputs['mueller_gartner_alfano'],
                                ]
        return outputs