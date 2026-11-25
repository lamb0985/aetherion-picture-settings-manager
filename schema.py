"""Public protocol metadata. No captured user values or device addresses."""
SERVICE = "vendor.vt.hs_av_service.IHisSystemApiAidl/default"
CONTEXT_KEYS = ("source", "signal_dr_type", "pic_mode")

# Observed Aetherion Max input IDs; other firmware may use different mappings.
SOURCE_NAMES = {4: "HDMI 1", 5: "HDMI 2", 6: "HDMI 3", 9: "Google TV"}

def source_name(source):
    return SOURCE_NAMES.get(source, f"Source {source}") if source is not None else None

SIGNALS = {
    0: "SDR 2K", 1: "SDR 4K", 2: "SDR 8K", 3: "HDR10",
    4: "HLG", 5: "Dolby Vision", 6: "HDR10+",
}
# Format names follow the research scanner; availability can vary by firmware.
MODES = {
    **{i: tuple(range(9)) for i in range(5)},
    5: (0, 1, 2, 4),
    6: (0, 1, 3, 4),
}
INDEXED = {
    "white_balance_20_point": ("20p_wb_point", 20, ("20p_wb_red", "20p_wb_green", "20p_wb_blue")),
    "gamma_calibration": ("gamma_calibration_level", 20, ("gamma_calibration_gain",)),
    "color_management": ("color_tuner_clr", 7, ("color_tuner_hue", "color_tuner_sat", "color_tuner_bri")),
}
# Only these adjustment setters have been exercised in batch operations so far.
# This is evidence metadata, not an authorization to write.
VERIFIED_SETTERS = {
    "color_temp": (0, 1, 2, 3),
    **{f"2p_wb_{kind}_{channel}": tuple(range(-25, 26))
       for kind in ("gain", "offset") for channel in ("red", "green", "blue")},
}
ENUMS = {
    "color_temp": {0:"Warm1", 1:"Warm2", 2:"Standard", 3:"Cool"},
    "color_space": {0:"Native", 1:"Auto", 2:"BT.709", 3:"DCI-P3", 4:"BT.2020", 5:"Adobe RGB"},
    "gamma_adjust": {0:"2.0", 1:"2.2", 2:"2.4", 3:"BT1886", 12:"HLG", 13:"ST2084"},
    "memc": {0:"Off", 1:"Custom", 2:"Film", 3:"Clear", 4:"Standard", 5:"Smooth"},
    "iris_mode": {0:"Off", 1:"Cinema 1", 2:"Cinema 2", 3:"Manual", 4:"Dynamic"},
}
# The native state field is deliberately preserved as an opaque integer.
# An observed enum or range is not evidence that every option is supported.

# Experimental live adjustment allowlist; validate current hardware range too.
LIVE_RANGES = {"backlight":[0,10],"contrast":[0,100],"brightness":[-50,50],"saturation":[0,100],"hue":[-50,50],"sharpness":[0,50],"memc_dejudder":[0,10],"memc_deblur":[0,10],"2p_wb_gain_red":[-25,25],"2p_wb_gain_green":[-25,25],"2p_wb_gain_blue":[-25,25],"2p_wb_offset_red":[-25,25],"2p_wb_offset_green":[-25,25],"2p_wb_offset_blue":[-25,25]}
LIVE_ENUMS = {"color_temp":[0,1,2,3],"memc":[0,1,2,3,4,5],"pq_apply":[0,1],"20p_wb":[0,1]}
EXTRA_SCAN_KEYS = ["temp_wb","ai_sr","nr","mpeg_nr","high_brightness","active_contrast","memc_dejudder","memc_deblur","backlight","brightness"]
