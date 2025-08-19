# --- filming side inference ---
LEFT = ["left_shoulder","left_elbow","left_wrist","left_hip","left_knee","left_ankle"]
RIGHT = ["right_shoulder","right_elbow","right_wrist","right_hip","right_knee","right_ankle"]

def infer_side(samples):
    def mean_conf(names):
        tot = cnt = 0.0
        for s in samples:
            lm = s.get("landmarks", {})
            for n in names:
                v = lm.get(n)
                if v and v[2] is not None:
                    tot += float(v[2]); cnt += 1
        return (tot / cnt) if cnt else 0.0
    ml = mean_conf(LEFT)
    mr = mean_conf(RIGHT)
    return ("left" if ml >= mr else "right", ml, mr)
