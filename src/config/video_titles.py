"""
Video title mapping for MV Face Recognition System.
Maps ASCII filenames to proper display titles for Gradio interface.
"""

# Video title mapping for HF Spaces deployment
VIDEO_TITLE_MAPPING = {
    # Clean ASCII filename -> Display title
    "mv1_zao_xing_zhi_zhan.mp4": "《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅",
    "mv2_shi_fa_zhi_zhan.mp4": "《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅",
    "mv3_nv_tuan_zhi_zhan.mp4": "《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅",
    "mv4_ji_xian_pai_mv.mp4": "《全民造星IV》極限拍MV",
    "mv5_bo_qian_re_shen.mp4": "《全民造星IV》播前熱身！率先表演《前傳》",
}

# Reverse mapping for backwards compatibility
TITLE_TO_FILENAME_MAPPING = {v: k for k, v in VIDEO_TITLE_MAPPING.items()}

def get_video_display_title(filename):
    """Get display title for a video filename."""
    return VIDEO_TITLE_MAPPING.get(filename, filename)

def get_video_filename(title):
    """Get filename for a video title."""
    return TITLE_TO_FILENAME_MAPPING.get(title, title)

def get_all_video_titles():
    """Get all available video titles."""
    return list(VIDEO_TITLE_MAPPING.values())

def get_all_video_filenames():
    """Get all available video filenames."""
    return list(VIDEO_TITLE_MAPPING.keys())