"""BlazePalm/hand geometry for the pinned Hailo-8 HEFs (RGB uint8 input).

Models: Google MediaPipe, compiled by AlbertaBeef/blaze_tutorial, Apache-2.0.
The tensor layouts and ROI transform are documented in docs/gestures.md.
Only the isolated system-Python worker imports NumPy/OpenCV/Hailo.
"""
import math

import cv2
import numpy as np


def palm_anchors():
    return np.asarray([((x + .5) / size, (y + .5) / size)
                       for size, repeats in ((24, 2), (12, 6))
                       for y in range(size) for x in range(size)
                       for _ in range(repeats)], dtype=np.float32)


ANCHORS = palm_anchors()


def letterbox(image, size=192):
    h, w = image.shape[:2]
    scale = size / max(w, h)
    nw, nh = round(w * scale), round(h * scale)
    left, top = (size - nw) // 2, (size - nh) // 2
    canvas = np.zeros((size, size, 3), np.uint8)
    canvas[top:top + nh, left:left + nw] = cv2.resize(image, (nw, nh))
    return canvas, scale, np.array([left, top], dtype=np.float32)


def decode_palms(outputs, scale, pad, threshold=.65):
    # Both heads emit raw convolution tensors; reshape in anchor order.
    scores = np.concatenate([outputs['palm_detection_lite/conv29'].reshape(-1),
                             outputs['palm_detection_lite/conv24'].reshape(-1)])
    boxes = np.concatenate([outputs['palm_detection_lite/conv30'].reshape(-1, 18),
                            outputs['palm_detection_lite/conv25'].reshape(-1, 18)])
    scores = 1 / (1 + np.exp(-np.clip(scores, -80, 80)))
    valid = np.flatnonzero((scores >= threshold) & np.isfinite(boxes).all(axis=1))
    if not len(valid):
        return []
    # Limit work before weighted NMS, including pathological model output.
    valid = valid[np.argsort(scores[valid])[-100:][::-1]]
    raw, centres = boxes[valid], ANCHORS[valid] * 192
    xy = raw[:, :2] + centres
    half = np.maximum(raw[:, 2:4], 0) / 2
    rects = np.c_[xy - half, xy + half]
    points = raw[:, 4:].reshape(-1, 7, 2) + centres[:, None, :]
    candidates = np.c_[rects, points.reshape(-1, 14)]
    confidence = scores[valid]
    result = []
    while len(candidates) and len(result) < 4:
        first = candidates[0, :4]
        area = np.prod(np.maximum(candidates[:, 2:4] - candidates[:, :2], 0), axis=1)
        overlap = np.prod(np.maximum(np.minimum(first[2:], candidates[:, 2:4]) -
                                     np.maximum(first[:2], candidates[:, :2]), 0), axis=1)
        group = overlap / np.maximum(area[0] + area - overlap, 1e-6) > .3
        group[0] = True
        merged = np.average(candidates[group], axis=0, weights=confidence[group])
        merged = (merged.reshape(-1, 2) - pad) / scale
        if min(merged[1] - merged[0]) > 8:
            result.append((merged, float(confidence[group].max())))
        candidates, confidence = candidates[~group], confidence[~group]
    return result


def hand_crop(image, palm):
    """Rotate the wrist→middle-knuckle axis upright, expand to the whole hand."""
    box, keypoints = palm[:2], palm[2:]
    wrist, middle = keypoints[0], keypoints[2]
    up = middle - wrist
    length = float(np.linalg.norm(up))
    if length < 3:
        raise ValueError('Palm orientation is ambiguous')
    up /= length
    right = np.array([-up[1], up[0]], np.float32)
    palm_size = float(max(box[1] - box[0]))
    centre = box.mean(axis=0) + up * palm_size * .5
    size = palm_size * 2.6
    source = np.float32([centre - right * size / 2 + up * size / 2,
                         centre - right * size / 2 - up * size / 2,
                         centre + right * size / 2 + up * size / 2])
    transform = cv2.getAffineTransform(source, np.float32([[0, 0], [0, 223], [223, 0]]))
    crop = cv2.warpAffine(image, transform, (224, 224))
    return crop, cv2.invertAffineTransform(transform), size


def classify_pose(points):
    """Conservative finger-curl rules; ambiguous poses never count as a press."""
    p = np.asarray(points, dtype=float)
    if p.shape != (21, 3) or not np.isfinite(p).all():
        return 'unknown'
    palm = np.linalg.norm(p[9] - p[0])
    if palm < 1e-6:
        return 'unknown'
    curled = extended = 0
    for base in (5, 9, 13, 17):
        mcp, pip, dip, tip = p[base:base + 4]
        a, b = mcp - pip, tip - pip
        cosine = np.dot(a, b) / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-6)
        angle = math.degrees(math.acos(float(np.clip(cosine, -1, 1))))
        ratio = np.linalg.norm(tip - p[0]) / max(np.linalg.norm(pip - p[0]), 1e-6)
        if ratio < 1.08 and (angle < 155 or np.linalg.norm(tip - mcp) < palm * .65):
            curled += 1
        elif ratio > 1.2 and angle > 150:
            extended += 1
    if curled == 4:
        return 'fist'
    if extended >= 3 and curled == 0:
        return 'open'
    return 'unknown'


class HandTracker:
    def __init__(self, palm_model, landmark_model, hand='any'):
        self.palm_model, self.landmark_model, self.hand = palm_model, landmark_model, hand
        self.previous = None
        self.previous_hand = None
        self.track = 0

    def infer(self, image):
        boxed, scale, pad = letterbox(image)
        output = self.palm_model.run_async(boxed).result(timeout=3)
        candidates = decode_palms(output, scale, pad)
        h, w = image.shape[:2]
        if self.previous is not None:
            candidates.sort(key=lambda item: np.linalg.norm(item[0][:2].mean(axis=0) / [w, h] - self.previous))
        for palm, score in candidates:
            try:
                crop, inverse, size = hand_crop(image, palm)
            except ValueError:
                continue
            output = self.landmark_model.run_async(crop).result(timeout=3)
            confidence = float(output['hand_landmark_lite/fc4'].reshape(-1)[0])
            # MediaPipe labels assume mirrored input; our CSI frames are unmirrored.
            handedness = float(output['hand_landmark_lite/fc3'].reshape(-1)[0])
            hand = 'left' if handedness > .5 else 'right'
            if not math.isfinite(confidence) or confidence < .75 or (self.hand != 'any' and hand != self.hand):
                continue
            raw = output['hand_landmark_lite/fc1'].reshape(21, 3)
            if not np.isfinite(raw).all():
                continue
            xy = np.c_[raw[:, :2], np.ones(21)] @ inverse.T
            xy /= [w, h]
            centre = xy[[0, 5, 9, 13, 17]].mean(axis=0)
            if np.any(centre < 0) or np.any(centre > 1):
                continue
            changed = (self.previous is None or self.previous_hand != hand or
                       np.linalg.norm(centre - self.previous) > .22)
            if changed:
                self.track += 1
            self.previous, self.previous_hand = centre, hand
            return {'tracked': True, 'track_id': self.track, 'hand': hand,
                    'x': round(float(centre[0]), 5), 'y': round(float(centre[1]), 5),
                    'pose': classify_pose(raw), 'confidence': round(confidence, 3),
                    'landmarks': np.round(xy, 5).tolist()}
        self.previous = self.previous_hand = None
        return {'tracked': False, 'pose': 'unknown', 'track_id': self.track}
