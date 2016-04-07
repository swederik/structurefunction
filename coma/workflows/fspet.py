import nipype.interfaces.io as nio           # Data i/o
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
import nipype.interfaces.fsl as fsl
import nipype.interfaces.freesurfer as fs
import coma.interfaces as ci
from nipype.workflows.misc.utils import select_aparc
from ..helpers import select_CSF, select_WM, select_GM
from coma.interfaces.glucose import calculate_SUV

fsl.FSLCommand.set_default_output_type('NIFTI_GZ')

def add_pet_stats_to_subjid(subject_id):
    return subject_id + "_PET_Stats.mat"

def add_pet_pve_stats_to_subjid(subject_id):
    return subject_id + "_PET_PVE_Stats.mat"

def create_freesurfer_pet_quantification_wf(name="fspetquant"):
    inputnode = pe.Node(
        interface=util.IdentityInterface(fields=["subject_id",
                                                 "subjects_dir",
                                                 "pet"]),
        name="inputnode")

    FreeSurferSource = pe.Node(
        interface=nio.FreeSurferSource(), name='fssource')
    mri_convert_Brain = pe.Node(
        interface=fs.MRIConvert(), name='mri_convert_Brain')
    mri_convert_Brain.inputs.out_type = 'niigz'
    mri_convert_Brain.inputs.no_change = True

    mri_convert_ROIs = mri_convert_Brain.clone("mri_convert_ROIs")
    mri_convert_T1 = mri_convert_Brain.clone("mri_convert_T1")

    fast_seg_T1 = pe.Node(interface=fsl.FAST(), name='fast_seg_T1')
    fast_seg_T1.inputs.segments = True
    fast_seg_T1.inputs.probability_maps = True

    coregister = pe.Node(interface=fsl.FLIRT(dof=6), name = 'coregister')
    coregister.inputs.cost = ('corratio')
    coregister.inputs.interp = 'trilinear'

    convertxfm = pe.Node(interface=fsl.ConvertXFM(), name = 'convertxfm')
    convertxfm.inputs.invert_xfm = True

    applyxfm_t1 = pe.Node(interface=fsl.ApplyXfm(), name = 'applyxfm_t1')
    applyxfm_t1.inputs.apply_xfm = True
    applyxfm_t1.inputs.interp = 'trilinear'

    applyxfm_gm = applyxfm_t1.clone("applyxfm_gm")
    applyxfm_gm.inputs.interp = 'nearestneighbour'
    applyxfm_wm = applyxfm_gm.clone("applyxfm_wm")
    applyxfm_csf = applyxfm_gm.clone("applyxfm_csf")

    applyxfm_rois = applyxfm_t1.clone("applyxfm_rois")
    applyxfm_rois.inputs.interp = 'nearestneighbour'

    applyxfm_CorrectedPET = pe.Node(interface=fsl.ApplyXfm(), name = 'applyxfm_CorrectedPET')
    applyxfm_CorrectedPET.inputs.apply_xfm = True
    applyxfm_CorrectedPET.inputs.interp = 'trilinear'

    pve_correction = pe.Node(interface=ci.PartialVolumeCorrection(), name = 'pve_correction')
    pve_correction.inputs.skip_atlas = False
    pve_correction.inputs.use_fs_LUT = True

    PET_ROI_values = pe.Node(interface=ci.RegionalValues(), name='PET_ROI_values')
    PET_PVE_ROI_values = pe.Node(interface=ci.RegionalValues(), name='PET_PVE_ROI_values')

    workflow = pe.Workflow(name=name)
    workflow.base_output_dir = name

    workflow.connect(
        [(inputnode, FreeSurferSource, [("subjects_dir", "subjects_dir")])])
    workflow.connect(
        [(inputnode, FreeSurferSource, [("subject_id", "subject_id")])])

    workflow.connect(
        [(FreeSurferSource, mri_convert_T1, [('T1', 'in_file')])])
    workflow.connect(
        [(FreeSurferSource, mri_convert_Brain, [('brain', 'in_file')])])
    workflow.connect(
        [(FreeSurferSource, mri_convert_ROIs, [(('aparc_aseg', select_aparc), 'in_file')])])

    workflow.connect(
        [(mri_convert_T1, coregister, [('out_file', 'reference')])])
    workflow.connect(
        [(mri_convert_Brain, fast_seg_T1, [('out_file', 'in_files')])])
    workflow.connect(
        [(inputnode, fast_seg_T1, [('subject_id', 'out_basename')])])
    workflow.connect(
        [(inputnode, coregister, [('pet', 'in_file')])])
    workflow.connect(
        [(coregister, convertxfm, [('out_matrix_file', 'in_file')])])
    workflow.connect(
        [(convertxfm, applyxfm_t1, [('out_file', 'in_matrix_file')])])
    workflow.connect(
        [(convertxfm, applyxfm_gm, [('out_file', 'in_matrix_file')])])
    workflow.connect(
        [(convertxfm, applyxfm_wm, [('out_file', 'in_matrix_file')])])
    workflow.connect(
        [(convertxfm, applyxfm_csf, [('out_file', 'in_matrix_file')])])
    workflow.connect(
        [(convertxfm, applyxfm_rois, [('out_file', 'in_matrix_file')])])

    workflow.connect(
        [(inputnode, applyxfm_t1, [('pet', 'reference')])])
    workflow.connect(
        [(mri_convert_T1, applyxfm_t1, [('out_file', 'in_file')])])

    workflow.connect(
        [(inputnode, applyxfm_gm, [('pet', 'reference')])])    
    workflow.connect([(fast_seg_T1, applyxfm_gm, [(('partial_volume_files', select_GM), 'in_file')])])
    
    workflow.connect(
        [(inputnode, applyxfm_wm, [('pet', 'reference')])])    
    workflow.connect([(fast_seg_T1, applyxfm_wm, [(('partial_volume_files', select_WM), 'in_file')])])
    
    workflow.connect(
        [(inputnode, applyxfm_csf, [('pet', 'reference')])])    
    workflow.connect([(fast_seg_T1, applyxfm_csf, [(('partial_volume_files', select_CSF), 'in_file')])])    

    workflow.connect(
        [(inputnode, applyxfm_rois, [('pet', 'reference')])])
    workflow.connect(
        [(mri_convert_ROIs, applyxfm_rois, [('out_file', 'in_file')])])

    workflow.connect(
        [(applyxfm_t1, pve_correction, [('out_file', 't1_file')])])
    workflow.connect(
        [(inputnode, pve_correction, [('pet', 'pet_file')])])
    workflow.connect(
        [(applyxfm_gm, pve_correction, [('out_file', 'grey_matter_file')])])
    workflow.connect(
        [(applyxfm_wm, pve_correction, [('out_file', 'white_matter_file')])])
    workflow.connect(
        [(applyxfm_csf, pve_correction, [('out_file', 'csf_file')])])
    workflow.connect(
        [(applyxfm_rois, pve_correction, [('out_file', 'roi_file')])])

    workflow.connect(
        [(pve_correction, applyxfm_CorrectedPET, [('mueller_gartner_rousset', 'in_file')])])
    workflow.connect(
        [(mri_convert_T1, applyxfm_CorrectedPET, [('out_file', 'reference')])])
    workflow.connect(
        [(coregister, applyxfm_CorrectedPET, [('out_matrix_file', 'in_matrix_file')])])


    # RegionalValues
    workflow.connect([(inputnode, PET_ROI_values, [(('subject_id', add_pet_stats_to_subjid), 'out_stats_file')])])
    workflow.connect([(mri_convert_ROIs, PET_ROI_values, [("out_file", "segmentation_file")])])
    workflow.connect([(coregister, PET_ROI_values, [("out_file", "in_files")])])

    workflow.connect([(inputnode, PET_PVE_ROI_values, [(('subject_id', add_pet_pve_stats_to_subjid), 'out_stats_file')])])
    workflow.connect([(mri_convert_ROIs, PET_PVE_ROI_values, [("out_file", "segmentation_file")])])
    workflow.connect([(applyxfm_CorrectedPET, PET_PVE_ROI_values, [("out_file", "in_files")])])

    output_fields = ["out_files", "pet_to_t1", "corrected_pet_to_t1", "pet_results_npz",
                     "pet_results_mat", "PET_stats_file", "PET_PVE_stats_file",
                     "T1", "ROIs", "brain"]

    outputnode = pe.Node(
        interface=util.IdentityInterface(fields=output_fields),
        name="outputnode")

    workflow.connect(
        [(pve_correction,        outputnode, [("out_files", "out_files")]),
         (pve_correction,        outputnode, [("results_numpy_npz", "pet_results_npz")]),
         (pve_correction,        outputnode, [("results_matlab_mat", "pet_results_mat")]),
         (applyxfm_CorrectedPET, outputnode, [("out_file", "corrected_pet_to_t1")]),
         (coregister,            outputnode, [("out_file", "pet_to_t1")]),
         (mri_convert_T1,        outputnode, [("out_file", "T1")]),
         (mri_convert_ROIs,      outputnode, [("out_file", "ROIs")]),
         (mri_convert_Brain,     outputnode, [("out_file", "brain")]),
         (PET_ROI_values,        outputnode, [("stats_file", "PET_stats_file")]),
         (PET_PVE_ROI_values,    outputnode, [("stats_file", "PET_PVE_stats_file")]),         
         ])

    return workflow