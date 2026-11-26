def home(flags):
    if flags.is_feature_enabled("py_flag"):
        return "new home"
    return "old home"