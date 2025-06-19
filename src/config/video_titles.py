"""
Video title mapping for MV Face Recognition System.
Maps ASCII filenames to proper display titles for Gradio interface.
"""

# Video title mapping for both ASCII and Unicode filenames
VIDEO_TITLE_MAPPING = {
    # Clean ASCII filename -> Display title
    "mv1_zao_xing_zhi_zhan.mp4": "📺 MV1: 造星の駅 (首部曲)",
    "mv2_shi_fa_zhi_zhan.mp4": "📺 MV2: 始発の駅 (次部曲)",
    "mv3_nv_tuan_zhi_zhan.mp4": "📺 MV3: 女團の駅 (三部曲)",
    "mv4_ji_xian_pai_mv.mp4": "📺 MV4: 極限拍MV",
    "mv5_bo_qian_re_shen.mp4": "📺 MV5: 播前熱身",
    
    # Unicode filename mapping for better display titles
    "1-《全民造星IV》主題曲 《前傳》MV 2021夏の首部曲：造星の駅.mp4": "📺 MV1: 造星の駅 (首部曲)",
    "2-《全民造星IV》主題曲 《前傳》MV 2021夏の次部曲：始発の駅.mp4": "📺 MV2: 始発の駅 (次部曲)",
    "3-《全民造星IV》主題曲 《前傳》MV 2021夏の三部曲：女團の駅.mp4": "📺 MV3: 女團の駅 (三部曲)",
    "4-《全民造星IV》極限拍MV.mp4": "📺 MV4: 極限拍MV",
    "5-《全民造星IV》播前熱身！率先表演《前傳》.mp4": "📺 MV5: 播前熱身",
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