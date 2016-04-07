def inclusion_filtering_mrtrix3(track_file, roi_file, fa_file, md_file, roi_names=None, registration_image_file=None, registration_matrix_file=None, prefix=None, tdi_threshold=10):
    import os
    import os.path as op
    import numpy as np
    import glob
    from coma.workflows.dmn import get_rois, save_heatmap
    from coma.interfaces.dti import write_trackvis_scene
    import nipype.pipeline.engine as pe
    import nipype.interfaces.fsl as fsl
    import nipype.interfaces.mrtrix as mrtrix
    import nipype.interfaces.diffusion_toolkit as dtk
    from nipype.utils.filemanip import split_filename
    import subprocess
    import shutil

    rois = get_rois(roi_file)

    fa_out_matrix = op.abspath("%s_FA.csv" % prefix)
    md_out_matrix = op.abspath("%s_MD.csv" % prefix)
    invLen_invVol_out_matrix = op.abspath("%s_invLen_invVol.csv" % prefix)

    subprocess.call(["tck2connectome", "-assignment_voxel_lookup",
        "-zero_diagonal",
        "-metric", "mean_scalar", "-image", fa_file,
        track_file, roi_file, fa_out_matrix])

    subprocess.call(["tck2connectome", "-assignment_voxel_lookup",
        "-zero_diagonal",
        "-metric", "mean_scalar", "-image", md_file,
        track_file, roi_file, md_out_matrix])

    subprocess.call(["tck2connectome", "-assignment_voxel_lookup",
        "-zero_diagonal",
        "-metric", "invlength_invnodevolume",
        track_file, roi_file, invLen_invVol_out_matrix])

    fa_matrix = np.loadtxt(fa_out_matrix)
    md_matrix = np.loadtxt(md_out_matrix)
    fa_matrix = fa_matrix + fa_matrix.T
    md_matrix = md_matrix + md_matrix.T

    if prefix is not None:
        npz_data = op.abspath("%s_connectivity.npz" % prefix)
    else:
        _, prefix, _ = split_filename(track_file)
        npz_data = op.abspath("%s_connectivity.npz" % prefix)
    np.savez(npz_data, fa=fa_matrix, md=md_matrix)

    summary_images = []
    out_files = [fa_out_matrix, md_out_matrix, invLen_invVol_out_matrix]
    return out_files, npz_data, summary_images