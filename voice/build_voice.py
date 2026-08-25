#!/usr/bin/env python3
"""
録音した ひとまとまりの音声ファイルを、
無音を手がかりに 1本ずつ 切り分けて、
音量をそろえ、圧縮して、HTML に 埋めこむための スクリプト。

つかいかた:
    # まず 切り分けの ようすを 確認（書きこみはしない）
    python3 build_voice.py --check rec_kuro.wav --chars kuro

    # 3人ぶん まとめて 処理して HTML に 埋めこむ
    python3 build_voice.py rec_kuro.wav rec_fute.wav rec_chap.wav \
            --chars kuro fute chap --html ../sansu-battle.html
"""
import argparse, base64, json, os, re, subprocess, sys, tempfile
import numpy as np

ORDER = ['start', 'hit1', 'hit2', 'hit3', 'combo', 'wrong', 'timeup', 'heal', 'ko', 'win']


# ---------------------------------------------------------------- 読みこみ
def load_audio(path, sr=44100):
    """ffmpeg で モノラル float32 に そろえて 読みこむ"""
    out = subprocess.run(
        ['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(sr),
         '-f', 'f32le', '-'],
        capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).astype(np.float64), sr


# ---------------------------------------------------------------- 切り分け
def split_by_silence(x, sr, want, gap=0.45, thresh_db=-42, pad=0.06):
    """
    無音で 区切って、ちょうど want 本に なるまで しきい値を さがす。
    gap: これより 長い無音を 区切りと みなす（秒）
    """
    win = int(sr * 0.02)
    n = len(x) // win
    env = np.abs(x[:n * win].reshape(n, win)).max(1)
    peak = env.max() if env.size else 1.0

    best = None
    for db in [thresh_db, -38, -46, -34, -50, -30, -54]:
        for g in [gap, 0.35, 0.6, 0.28, 0.8]:
            th = peak * (10 ** (db / 20.0))
            loud = env > th
            segs, i = [], 0
            need = max(1, int(g / 0.02))
            while i < n:
                if loud[i]:
                    j = i
                    quiet = 0
                    while j < n:
                        if loud[j]:
                            quiet = 0
                        else:
                            quiet += 1
                            if quiet >= need:
                                break
                        j += 1
                    end = j - quiet + 1
                    segs.append((i, min(end, n)))
                    i = j
                i += 1
            segs = [s for s in segs if (s[1] - s[0]) * 0.02 >= 0.18]
            if best is None or abs(len(segs) - want) < abs(len(best[0]) - want):
                best = (segs, db, g)
            if len(segs) == want:
                return _cut(x, sr, segs, win, pad), db, g
    return _cut(x, sr, best[0], win, pad), best[1], best[2]


def _cut(x, sr, segs, win, pad):
    p = int(sr * pad)
    out = []
    for a, b in segs:
        s = max(0, a * win - p)
        e = min(len(x), b * win + p)
        out.append(x[s:e])
    return out


# ---------------------------------------------------------------- 音量そろえ
def normalize(seg, target_rms=0.08, ceiling=0.89):
    if seg.size == 0:
        return seg
    rms = np.sqrt((seg ** 2).mean())
    if rms < 1e-6:
        return seg
    g = min(target_rms / rms, ceiling / (np.abs(seg).max() + 1e-9))
    y = seg * g
    # 前後を なめらかに
    f = min(int(len(y) * 0.02), 400)
    if f > 2:
        y[:f] *= np.linspace(0, 1, f)
        y[-f:] *= np.linspace(1, 0, f)
    return y


# ---------------------------------------------------------------- 書き出し
ENC = {'mp3': ('libmp3lame', 'mp3', 'audio/mpeg'),
       'm4a': ('aac', 'm4a', 'audio/mp4')}


def encode(seg, sr, fmt='mp3', kbps=48):
    codec, ext, mime = ENC[fmt]
    with tempfile.TemporaryDirectory() as d:
        raw = os.path.join(d, 'a.f32')
        out = os.path.join(d, 'a.' + ext)
        seg.astype(np.float32).tofile(raw)
        cmd = ['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(sr), '-ac', '1',
               '-i', raw, '-c:a', codec, '-b:a', f'{kbps}k']
        if fmt == 'm4a':
            cmd += ['-movflags', '+faststart']
        cmd.append(out)
        subprocess.run(cmd, check=True)
        return open(out, 'rb').read(), mime


# ---------------------------------------------------------------- セリフ表
def read_lines(html):
    s = open(html, encoding='utf-8').read()
    m = re.search(r'const LINES = (\{.*?\n\};)', s, re.S)
    js = m.group(1).rstrip(';')
    js = re.sub(r'(\n\s*)(\w+)\s*:', r'\1"\2":', js)
    js = js.replace("'", '"')
    js = re.sub(r',(\s*[}\]])', r'\1', js)
    return json.loads(js)


def ids_for(lines, char):
    out = []
    for k in ORDER:
        for i in range(len(lines[char][k])):
            out.append(f'{char}_{k}_{i+1}')
    return out


# ---------------------------------------------------------------- 埋めこみ
def embed(html, voices):
    s = open(html, encoding='utf-8').read()
    blob = 'const VOICEFILES = ' + json.dumps(voices, ensure_ascii=False) + ';\n'
    if 'const VOICEFILES = ' in s:
        i = s.index('const VOICEFILES = ')
        j = s.index(';\n', i) + 2
        s = s[:i] + blob + s[j:]
    else:
        anchor = '/* ---------- あいての音声 ---------- */'
        s = s.replace(anchor, blob + anchor, 1)
    open(html, 'w', encoding='utf-8').write(s)
    return len(blob)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--chars', nargs='+', required=True,
                    help='ファイルに対応する キャラID（kuro fute chap）')
    ap.add_argument('--html', default='../sansu-battle.html')
    ap.add_argument('--check', action='store_true', help='切り分けの確認だけ')
    ap.add_argument('--kbps', type=int, default=48)
    ap.add_argument('--format', choices=['mp3','m4a'], default='mp3')
    a = ap.parse_args()

    lines = read_lines(a.html)
    voices, total = {}, 0
    for path, ch in zip(a.files, a.chars):
        want_ids = ids_for(lines, ch)
        x, sr = load_audio(path)
        segs, db, gap = split_by_silence(x, sr, len(want_ids))
        print(f'\n[{ch}] {os.path.basename(path)}  {len(x)/sr:.1f}秒')
        print(f'   しきい値 {db}dB / 無音 {gap}秒  →  {len(segs)}本 '
              f'（必要 {len(want_ids)}本）')
        if len(segs) != len(want_ids):
            print('   ⚠ 本数が合いません。--check で 確認してください。')
        for i, (sid, seg) in enumerate(zip(want_ids, segs)):
            txt = lines[ch][sid.rsplit('_', 2)[1]][int(sid.rsplit('_', 1)[1]) - 1]
            if a.check:
                print(f'   {i+1:3d} {len(seg)/sr:5.2f}秒  {sid:18s} {txt}')
                continue
            data, mime = encode(normalize(seg), sr, a.format, a.kbps)
            total += len(data)
            voices[sid] = f'data:{mime};base64,' + base64.b64encode(data).decode()
    if a.check:
        return
    n = embed(a.html, voices)
    print(f'\n埋めこみ完了: {len(voices)}本 / 音声 {total/1024:.0f}KB '
          f'/ base64 {n/1024:.0f}KB')


if __name__ == '__main__':
    main()
