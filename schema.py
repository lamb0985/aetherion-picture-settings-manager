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
}
# The native state field is deliberately preserved as an opaque integer.
# An observed enum or range is not evidence that every option is supported.

# Experimental live adjustment allowlist; validate current hardware range too.
LIVE_RANGES = {"backlight":[0,10],"contrast":[0,100],"brightness":[-50,50],"saturation":[0,100],"hue":[-50,50],"sharpness":[0,50],"memc_dejudder":[0,10],"memc_deblur":[0,10],"2p_wb_gain_red":[-25,25],"2p_wb_gain_green":[-25,25],"2p_wb_gain_blue":[-25,25],"2p_wb_offset_red":[-25,25],"2p_wb_offset_green":[-25,25],"2p_wb_offset_blue":[-25,25]}
LIVE_ENUMS = {"color_temp":[0,1,2,3],"memc":[0,1,2,3,4,5],"pq_apply":[0,1],"20p_wb":[0,1]}
EXTRA_SCAN_KEYS = ["temp_wb","ai_sr","nr","mpeg_nr","high_brightness","active_contrast","memc_dejudder","memc_deblur","backlight","brightness"]

# Discrete values from native preference XML and laser-specific arrays.
LIVE_ENUMS.update({"high_dynamic":[0,1],"dark_detail":[0,1],"active_contrast":[0,1,2,3],"high_brightness":[0,1],"hdr_enhancer":[0,1],"temp_wb":[0,1],"color_space":[0,1,2,3,4],"dynamic_color_enhancer":[0,1,2,3],"gradient_smooth":[0,1,2,3],"ai_sr":[0,1,2,3],"nr":[0,1,2,3],"mpeg_nr":[0,1,2,3],"gamma_adjust":[0,1,2,3,12,13]})

# Shared inventory: native names returned by the hardware coverage audit.
NATIVE_READ_KEYS = set("""20p_wb 20p_wb_blue 20p_wb_green 20p_wb_point 20p_wb_red
2p_wb 2p_wb_gain_blue 2p_wb_gain_green 2p_wb_gain_red 2p_wb_offset_blue 2p_wb_offset_green 2p_wb_offset_red
3d 3d_to_2d active_contrast ai_energy_saving ai_sr aipq aspect_ratio auto_color_temp auto_game auto_white_balance
backlight brightness color_space color_temp color_tuner color_tuner_bri color_tuner_clr color_tuner_hue color_tuner_sat contrast
dark_detail dlp_turbo dolbypc dynamic_backlight dynamic_color_enhancer dynamic_tone_mapping fast_backlight_control fps freesync
gamma_adjust gamma_calibration gamma_calibration_gain gamma_calibration_level gradient_smooth hdmi_dynamic_range hdr_enhancer
high_altitude high_brightness high_dynamic hsr hue imax_state instant_peaking is_3d_on is_dolby is_game is_hdr is_hdr10_plus is_support_dolby_iq is_uhd
laser_type light_sensor light_sensor_shift local_dimming low_blue_light low_noise memc memc_deblur memc_dejudder motion_clearness mpeg_nr nr
peaking pic_mode pq_apply precision_detail rbe_reduction rgb_only saturation screen_size sharpness signal_dr_type source stable_peaking super_resolution temp_wb vrr vrr_plus""".split()) | set(LIVE_RANGES) | set(LIVE_ENUMS) | set(CONTEXT_KEYS) | set(EXTRA_SCAN_KEYS)

def picture_key(key):
    return isinstance(key,str) and key.replace("_","").isalnum() and "iris" not in key.lower()

def parameter_inventory(seed):
    keys=set(NATIVE_READ_KEYS)
    for group in seed.get("parameter_candidates",{}).values():
        if isinstance(group,list):
            keys.update(k for k in group if picture_key(k))
    for group in seed.get("profiles",{}).values():
        for profile in group.get("profiles",{}).values():
            keys.update(k for k in profile.get("settings",{}) if picture_key(k))
    return sorted(k for k in keys if picture_key(k))

def picture_snapshot(data):
    # Preserve historical files; exclude removed attributes from current application views.
    for group in data.get("profiles",{}).values():
        for profile in group.get("profiles",{}).values():
            profile["settings"]={k:v for k,v in profile.get("settings",{}).items() if picture_key(k)}
    data["parameter_candidates"]={k:[v for v in values if picture_key(v)] if isinstance(values,list) else values
                                  for k,values in data.get("parameter_candidates",{}).items() if picture_key(k)}
    data["menu_enumerations"]={k:v for k,v in data.get("menu_enumerations",{}).items() if picture_key(k)}
    return data
