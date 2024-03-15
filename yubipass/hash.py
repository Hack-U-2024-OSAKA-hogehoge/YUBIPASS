import hashlib
import os
import random
import sys

import cv2
import numpy as np
from django.conf import settings


# 角度分布から文字列変換
def angles2str(per_angle):
    strcode =[]
    for counts in per_angle:

        if counts != [None]:

            # countsを比率に変換
            ratio = [count / sum(counts) for count in counts]

            # 標準偏差を計算
            std = np.std(ratio)

            # 標準偏差が小さい場合はSを追加
            if std < 0.2:
                strcode.append("S")
                continue

            # 文字変換
            max_value = max(counts)
            max_index = counts.index(max_value)
            strcode.append(str(max_index))

        else:

            strcode.append("E")

    # リストを文字列として出力
    output_str = "".join(strcode)

    return output_str


# 画像領域分割
def region_division(image, region, division):

    # 領域分割
    height, width = image.shape[:2]
    region_height = height // division
    region_width = width // division

    row = region // division
    col = region % division

    start_x = region_width * col
    end_x = start_x + region_width
    start_y = region_height * row
    end_y = start_y + region_height

    return image[start_y:end_y, start_x:end_x]


# 指紋傾き検出
def detect_angles(image, T, M):

    angles = []

    # 直線検出
    lines = cv2.HoughLinesP(image, 1, np.pi / 180, threshold=T, minLineLength=M, maxLineGap=1)

    if lines is not None:

        # 傾き算出
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if angle < 0:
                angle += 180

            angles.append(angle)

    return angles


# 傾き分布処理
def angle_distribution(angles, per_angle):

    recounts = []

    # 傾き分布調査
    counts = list(np.histogram(angles, bins=[0, 22.5, 45, 75, 90, 105, 135, 157.5, 180])[0])

    # 横/左斜め/縦/右斜めの分布に変換
    for i in range(0,7,2):
        if  0 == i:
            recounts.append(counts[0]+counts[-1])
        else:
            recounts.append(counts[i-1]+counts[i])

    per_angle.append(recounts)


# 画像加工処理
def image_processing(image):

    thickness_factor = 17
    square_size = 150

    # ガウシアンフィルターを適用
    image = cv2.GaussianBlur(image, (3, 3), 0)

    # グレースケール変換
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 二値化変換
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)

    # カーネルの作成
    kernel_size = thickness_factor // 2
    if thickness_factor % 2 == 0:
        kernel_size -= 1
    kernel = np.ones((kernel_size, kernel_size), np.uint8)

    # 膨張処理
    binary = cv2.dilate(binary, kernel, iterations=1)

    # 輪郭の検出
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 楕円を検出
    for contour in contours:
        if len(contour) >= 20:
            ellipse = cv2.fitEllipse(contour)
            center = ellipse[0]

    # 楕円の内部を表すマスクを作成
    mask = np.zeros_like(gray)
    cv2.ellipse(mask, ellipse, (255,255,255), -1)

    # 楕円の内部以外を白にする
    image[mask == 0] = [255,255,255]

    # 楕円の中心点を取得
    center_x = int(center[0])
    center_y = int(center[1])

    # 正方形画像を作成
    square_image = np.ones((square_size, square_size, 3), dtype=np.uint8) * 255

    # 正方形の中心座標を計算
    new_center_x = square_size // 2
    new_center_y = square_size // 2

    # 元画像から切り取る領域の左上座標を計算
    start_x = max(0, center_x - square_size // 2)
    start_y = max(0, center_y - square_size // 2)

    # 元画像から切り取る領域の右下座標を計算
    end_x = min(image.shape[1], center_x + square_size // 2)
    end_y = min(image.shape[0], center_y + square_size // 2)

    # 元画像から正方形の領域を切り取り
    cropped_image = image[start_y:end_y, start_x:end_x]

    # 正方形画像に切り取った領域を貼り付け
    new_start_x = new_center_x - (center_x - start_x)
    new_start_y = new_center_y - (center_y - start_y)
    new_end_x = new_start_x + (end_x - start_x)
    new_end_y = new_start_y + (end_y - start_y)
    square_image[new_start_y:new_end_y, new_start_x:new_end_x] = cropped_image

    return square_image


#元画像を2値化
def color2binary(image):

  # グレースケール変換
  gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

  # 二値化変換
  _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)

  return binary


# 領域縮小処理
def image_reduction(image, thickness_factor):

    # 色を反転させる
    inverted_img = cv2.bitwise_not(image)

    # カーネルの作成
    kernel_size = thickness_factor // 2
    if thickness_factor % 2 == 0:
        kernel_size -= 1
    kernel = np.ones((kernel_size, kernel_size), np.uint8)

    # 収縮処理を行う
    result = cv2.erode(inverted_img, kernel, iterations=1)

    return color2binary(cv2.bitwise_not(result))

# 指紋画像から文字列に変換
def fingerprint2string(image):

    per_angle = []
    num = 0
    contraction = 4
    division = 3
    threshold = 20
    minLineLength =3


    # 画像加工処理
    image = image_processing(image)
    binary = color2binary(image)

    # 画像を分割数に応じた直線検出
    while True:

        for i in range(division**2):

            angles = detect_angles(region_division(binary, i, division), threshold, minLineLength)

            num += len(angles)

            if len(angles) > 3:

                angle_distribution(angles, per_angle)

            else:
                per_angle.append([None])

        if num > 300:

            contraction += 1

            if contraction >= 15:

                return None

            binary = image_reduction(image, contraction)

            num = 0
            per_angle = []

        else:

            break

    # 傾き分布を文字列に変換
    return angles2str(per_angle)



# 上部のピクセルを白色にする(予備)
def make_top_pixels_white(image, num_pixels):
    # 画像の高さと幅を取得
    height, width = image.shape[:2]

    # 上部のピクセル数が画像の高さよりも大きい場合、全体を白色に変更
    if num_pixels >= height:
        return np.ones_like(image) * 255

    # 上部のピクセルを白色にする
    image[:num_pixels, :] = 255

    return image


def xxhash32(data):
    state = 0x01234567  # 初期値
    for byte in data:
        state = (state * 0x13377331 + byte) & 0xFFFFFFFF
    return hex(state)[2:]

# 文字列をシャッフルする関数
def shuffle_string(s):
    random.seed(s)  # シードを固定して乱数の再現性を確保
    shuffled = ''.join(random.sample(s, len(s)))
    return shuffled

def get_hash(url):
    
    if os.name == "nt":
            slash = "\\"
    else:
        slash = "/"

    image = cv2.imread(os.path.abspath(settings.BASE_DIR) + slash + "static" + slash + "img" + slash + "finger.bmp")
    # make_top_pixels_white(image, 30)
    # print("fingerprint2string:"+fingerprint2string(image))
    fingerprint_len9=fingerprint2string(image)
    
    if fingerprint_len9 == None:
        print("指紋画像が不正です")
    else:
        #4つ角を無くす
        fingerprint_len5=fingerprint_len9[1]+fingerprint_len9[3:6]+fingerprint_len9[7]
        
        print("fingerprint_len5:"+fingerprint_len5)
        
        text_1 = str(url)
        text_2 = fingerprint_len5

        # SHA-256でハッシュ化
        hash_1 = hashlib.sha256(text_1.encode()).hexdigest()
        # print("hash_1:"+hash_1)
        hash_2 = hashlib.sha256(text_2.encode()).hexdigest()
        # print("hash_2:"+hash_2)

        # 16進数のハッシュ値を2進数に変換
        binary_hash_1 = bin(int(hash_1, 16))[2:]
        binary_hash_2 = bin(int(hash_2, 16))[2:]

        # ハッシュ値の長さを揃えるために0を追加する
        max_length = max(len(binary_hash_1), len(binary_hash_2))
        binary_hash_1 = binary_hash_1.zfill(max_length)
        binary_hash_2 = binary_hash_2.zfill(max_length)

        # 排他的論理和を取る
        result = ''.join(str(int(x) ^ int(y)) for x, y in zip(binary_hash_1, binary_hash_2))

        # xxHash 32でハッシュ化
        hash_xx = xxhash32(result.encode())
        print("xxHash32の値：" + hash_xx)

        # xxHash 32を10進数に変換
        hash32_10 = int(hash_xx, 16)
        print("10進数に変換：" + str(hash32_10))

        # 100で割った余りをKariPassとする
        KariPass = hash32_10 % 100
        print("条件：" + str(KariPass))



        # パスワード条件分岐
        if KariPass == 0:
            Pass = hash_xx +"1Xv"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 0.")
            print("Pass:" + Pass)
        elif KariPass == 1:
            Pass = hash_xx +"9Fe"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 1.")
            print("Pass:" + Pass)
        elif KariPass == 2:
            Pass = hash_xx +"3Uq"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 2.")
            print("Pass:" + Pass)
        elif KariPass == 3:
            Pass = hash_xx +"6Pm"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 3.")
            print("Pass:" + Pass)
        elif KariPass == 4:
            Pass = hash_xx +"2Tz"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 4.")
            print("Pass:" + Pass)
        elif KariPass == 5:
            Pass = hash_xx +"0Yb"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 5.")
            print("Pass:" + Pass)
        elif KariPass == 6:
            Pass = hash_xx +"5Wi"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 6.")
            print("Pass:" + Pass)
        elif KariPass == 7:
            Pass = hash_xx +"8Jg"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 7.")
            print("Pass:" + Pass)
        elif KariPass == 8:
            Pass = hash_xx +"4Mo"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 8.")
            print("Pass:" + Pass)
        elif KariPass == 9:
            Pass = hash_xx +"7Rh"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 9.")
            print("Pass:" + Pass)
        elif KariPass == 10:
            Pass = hash_xx+"1Nk"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 10.")
            print("Pass:" + Pass)
        elif KariPass == 11:
            Pass = hash_xx +"9Xw"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 11.")
            print("Pass:" + Pass)
        elif KariPass == 12:
            Pass = hash_xx +"3Ch"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 12.")
            print("Pass:" + Pass)
        elif KariPass == 13:
            Pass = hash_xx +"6Vt"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 13.")
            print("Pass:" + Pass)
        elif KariPass == 14:
            Pass = hash_xx +"2Gd"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 14.")
            print("Pass:" + Pass)
        elif KariPass == 15:
            Pass = hash_xx +"0Aq"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 15.")
            print("Pass:" + Pass)
        elif KariPass == 16:
            Pass = hash_xx +"5Ya"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 16.")
            print("Pass:" + Pass)
        elif KariPass == 17:
            Pass = hash_xx +"8Dp"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 17.")
            print("Pass:" + Pass)
        elif KariPass == 18:
            Pass = hash_xx +"4Fu"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 18.")
            print("Pass:" + Pass)
        elif KariPass == 19:
            Pass = hash_xx +"7Om"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 19.")
            print("Pass:" + Pass)
        elif KariPass == 20:
            Pass = hash_xx +"1Hr"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 20.")
            print("Pass:" + Pass)
        elif KariPass == 21:
            Pass = hash_xx +"9Lc"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 21.")
            print("Pass:" + Pass)
        elif KariPass == 22:
            Pass = hash_xx +"3Wx"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 22.")
            print("Pass:" + Pass)
        elif KariPass == 23:
            Pass = hash_xx +"6Ev"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 23.")
            print("Pass:" + Pass)
        elif KariPass == 24:
            Pass = hash_xx +"2Kj"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 24.")
            print("Pass:" + Pass)
        elif KariPass == 25:
            Pass = hash_xx +"0Bs"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 25.")
            print("Pass:" + Pass)
        elif KariPass == 26:
            Pass = hash_xx +"5Zm"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 26.")
            print("Pass:" + Pass)
        elif KariPass == 27:
            Pass = hash_xx +"8Qi"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 27.")
            print("Pass:" + Pass)
        elif KariPass == 28:
            Pass = hash_xx +"4Pi"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 28.")
            print("Pass:" + Pass)
        elif KariPass == 29:
            Pass = hash_xx+"7Lt"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 29.")
            print("Pass:" + Pass)
        elif KariPass == 30:
            Pass = hash_xx+"1Uw"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 30.")
            print("Pass:" + Pass)
        elif KariPass == 31:
            Pass = hash_xx +"9Fi"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 31.")
            print("Pass:" + Pass)
        elif KariPass == 32:
            Pass = hash_xx+"3Xb"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 32.")
            print("Pass:" + Pass)
        elif KariPass == 33:
            Pass = hash_xx+"6Og"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 33.")
            print("Pass:" + Pass)
        elif KariPass == 34:
            Pass = hash_xx+"2Rz"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 34.")
            print("Pass:" + Pass)
        elif KariPass == 35:
            Pass = hash_xx+"OVq"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 35.")
            print("Pass:" + Pass)
        elif KariPass == 36:
            Pass = hash_xx+"5Nd"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 36.")
            print("Pass:" + Pass)
        elif KariPass == 37:
            Pass = hash_xx+"8Ct"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 37.")
            print("Pass:" + Pass)
        elif KariPass == 38:
            Pass = hash_xx+"4Mp"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 38.")
            print("Pass:" + Pass)
        elif KariPass == 39:
            Pass = hash_xx+"7Ya"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 39.")
            print("Pass:" + Pass)
        elif KariPass == 40:
            Pass = hash_xx+"1Jk"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 40.")
            print("Pass:" + Pass)
        elif KariPass == 41:
            Pass = hash_xx+"9Gu"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 41.")
            print("Pass:" + Pass)
        elif KariPass == 42:
            Pass = hash_xx+"3Ho"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 42.")
            print("Pass:" + Pass)
        elif KariPass == 43:
            Pass = hash_xx+"6Wi"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 43.")
            print("Pass:" + Pass)
        elif KariPass == 44:
            Pass = hash_xx+"2Sq"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 44.")
            print("Pass:" + Pass)
        elif KariPass == 45:
            Pass = hash_xx+"0Fd"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 45.")
            print("Pass:" + Pass)
        elif KariPass == 46:
            Pass = hash_xx+"5Er"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 46.")
            print("Pass:" + Pass)
        elif KariPass == 47:
            Pass = hash_xx+"8Zx"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 47.")
            print("Pass:" + Pass)
        elif KariPass == 48:
            Pass = hash_xx+"4Lb"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 48.")
            print("Pass:" + Pass)
        elif KariPass == 49:
            Pass = hash_xx+"7Cv"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 49.")
            print("Pass:" + Pass)
        elif KariPass == 50:
            Pass = hash_xx+"1Pi"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 50.")
            print("Pass:" + Pass)
        elif KariPass == 51:
            Pass = hash_xx+"9Tm"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 51.")
            print("Pass:" + Pass)
        elif KariPass == 52:
            Pass = hash_xx+"3Sa"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 52.")
            print("Pass:" + Pass)
        elif KariPass == 53:
            Pass = hash_xx+"6Yc"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 53.")
            print("Pass:" + Pass)
        elif KariPass == 54:
            Pass = hash_xx+"2Dq"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 54.")
            print("Pass:" + Pass)
        elif KariPass == 55:
            Pass = hash_xx+"0Rh"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 55.")
            print("Pass:" + Pass)
        elif KariPass == 56:
            Pass = hash_xx+"5Kg"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 56.")
            print("Pass:" + Pass)
        elif KariPass == 57:
            Pass = hash_xx+"8Wj"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 57.")
            print("Pass:" + Pass)
        elif KariPass == 58:
            Pass = hash_xx+"4Bx"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 58.")
            print("Pass:" + Pass)
        elif KariPass == 59:
            Pass = hash_xx +"7Vu"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 59.")
            print("Pass:" + Pass)
        elif KariPass == 60:
            Pass = hash_xx +"1Gm"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 60.")
            print("Pass:" + Pass)
        elif KariPass == 61:
            Pass = hash_xx +"9Pt"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 61.")
            print("Pass:" + Pass)
        elif KariPass == 62:
            Pass = hash_xx +"3Lz"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 62.")
            print("Pass:" + Pass)
        elif KariPass == 63:
            Pass = hash_xx +"6Qi"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 63.")
            print("Pass:" + Pass)
        elif KariPass == 64:
            Pass = hash_xx +"2Ow"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 64.")
            print("Pass:" + Pass)
        elif KariPass == 65:
            Pass = hash_xx+"0Ja"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 65.")
            print("Pass:" + Pass)
        elif KariPass == 66:
            Pass = hash_xx +"5Ux"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 66.")
            print("Pass:" + Pass)
        elif KariPass == 67:
            Pass = hash_xx+"8Ho"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 67.")
            print("Pass:" + Pass)
        elif KariPass == 68:
            Pass = hash_xx +"4Fd"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 68.")
            print("Pass:" + Pass)
        elif KariPass == 69:
            Pass = hash_xx+"7Ed"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 69.")
            print("Pass:" + Pass)
        elif KariPass == 70:
            Pass = hash_xx+"1Wv"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 70.")
            print("Pass:" + Pass)
        elif KariPass == 71:
            Pass = hash_xx+"9Mo"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 71.")
            print("Pass:" + Pass)
        elif KariPass == 72:
            Pass = hash_xx+"3Si"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 72.")
            print("Pass:" + Pass)
        elif KariPass == 73:
            Pass = hash_xx +"6Dp"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 73.")
            print("Pass:" + Pass)
        elif KariPass == 74:
            Pass = hash_xx +"2Fu"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 74.")
            print("Pass:" + Pass)
        elif KariPass == 75:
            Pass = hash_xx +"0Om"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 75.")
            print("Pass:" + Pass)
        elif KariPass == 76:
            Pass = hash_xx+"5Hr"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 76.")
            print("Pass:" + Pass)
        elif KariPass == 77:
            Pass = hash_xx+"8Lc"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 77.")
            print("Pass:" + Pass)
        elif KariPass == 78:
            Pass = hash_xx +"4Wx"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 78.")
            print("Pass:" + Pass)
        elif KariPass == 79:
            Pass = hash_xx+"7Ev"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 79.")
            print("Pass:" + Pass)
        elif KariPass == 80:
            Pass = hash_xx+"1Kj"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 80.")
            print("Pass:" + Pass)
        elif KariPass == 81:
            Pass = hash_xx +"9Bs"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 81.")
            print("Pass:" + Pass)
        elif KariPass == 82:
            Pass = hash_xx +"3ZM"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 82.")
            print("Pass:" + Pass)
        elif KariPass == 83:
            Pass = hash_xx +"6Qi"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 83.")
            print("Pass:" + Pass)
        elif KariPass == 84:
            Pass = hash_xx +"2Ow"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 84.")
            print("Pass:" + Pass)
        elif KariPass == 85:
            Pass = hash_xx +"Oja"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 85.")
            print("Pass:" + Pass)
        elif KariPass == 86:
            Pass = hash_xx +"5Ux"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 86.")
            print("Pass:" + Pass)
        elif KariPass == 87:
            Pass = hash_xx +"8Ho"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 87.")
            print("Pass:" + Pass)
        elif KariPass == 88:
            Pass = hash_xx +"4Fd"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 88.")
            print("Pass:" + Pass)
        elif KariPass == 89:
            Pass = hash_xx+"7Eb"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 89.")
            print("Pass:" + Pass)
        elif KariPass == 90:
            Pass = hash_xx+"1Wv"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 90.")
            print("Pass:" + Pass)
        elif KariPass == 91:
            Pass = hash_xx +"9Mo"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 91.")
            print("Pass:" + Pass)
        elif KariPass == 92:
            Pass = hash_xx +"3Si"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 92.")
            print("Pass:" + Pass)
        elif KariPass == 93:
            Pass = hash_xx +"6Dp"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 93.")
            print("Pass:" + Pass)
        elif KariPass == 94:
            Pass = hash_xx +"2Fu"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 94.")
            print("Pass:" + Pass)
        elif KariPass == 95:
            Pass = hash_xx +"0Rq"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 95.")
            print("Pass:" + Pass)
        elif KariPass == 96:
            Pass = hash_xx +"5Hr"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 96.")
            print("Pass:" + Pass)
        elif KariPass == 97:
            Pass = hash_xx +"8Lc"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 97.")
            print("Pass:" + Pass)
        elif KariPass == 98:
            Pass = hash_xx +"7Wx"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 98.")
            print("Pass:" + Pass)
        elif KariPass == 99:
            Pass = hash_xx +"1Fd"
            Pass = shuffle_string(Pass)  # Passの値をシャッフル
            print("Number is 99.")
            print("Pass:" + Pass)
            
        return Pass