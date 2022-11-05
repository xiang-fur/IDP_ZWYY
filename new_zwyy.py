#  Copyright (c) 2022. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.
import base64
import json
import os
import threading
import time

import jsonpath
import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

from ddddocr_m import DdddOcr

jsonfile = './zwyy_json.json'  # Json位置，使用cron运行请写完整路径
tomorrow_date = str(time.strftime('%Y-%m-%d', time.localtime(time.time() + 86400)))

headers = {
    "Accept": "application/json, text/plain, */*",
    "Host": "zwyy.cidp.edu.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/92.0.4515.159 Safari/537.36"}

ocr = DdddOcr()  # 初始化ocr
res_lock = threading.Lock()


# 推送&显示返回
def _push(text):
    print(text)
    try:
        push_url = f"https://api2.pushdeer.com/message/push?pushkey={pushkey}&text={text}"
        requests.get(push_url, timeout=3, verify=False)
    except:
        with open('./zwyy.log', 'a+') as f:
            print(text, file=f)


def to_print(text):
    print('\r' + str(text), end='', flush=True)


# 版本信息
def v_info():
    logo_text = "                                                          \n" \
                "██╗██████╗ ██████╗    ███████╗██╗    ██╗██╗   ██╗██╗   ██╗\n" \
                "██║██╔══██╗██╔══██╗   ╚══███╔╝██║    ██║╚██╗ ██╔╝╚██╗ ██╔╝\n" \
                "██║██║  ██║██████╔╝     ███╔╝ ██║ █╗ ██║ ╚████╔╝  ╚████╔╝ \n" \
                "██║██║  ██║██╔═══╝     ███╔╝  ██║███╗██║  ╚██╔╝    ╚██╔╝  \n" \
                "██║██████╔╝██║███████╗███████╗╚███╔███╔╝   ██║      ██║   \n" \
                "╚═╝╚═════╝ ╚═╝╚══════╝╚══════╝ ╚══╝╚══╝    ╚═╝      ╚═╝   \n" \
                "                                                          \n"
    update_text = "版本更新说明\n版本v1.0，基于新座位预约系统编写，基本功能正常使用，第一个发布版。\n版本v1.1，优化显示，独立部分模块，允许未到时间提前登录的，概率上加快抢座位速度。\n版本v1.2" \
                  "，精简化ddddocr，缩小生成文件体积,同时易于生成。\n "
    print(logo_text)


# 加载Json
def load_zwyy_json():
    if not os.path.isfile(jsonfile):
        print('未找到zwyy_json.json，请检查！')
        return "JsonNotFile"
    zwyy_json = json.load(open(jsonfile, 'r'))
    global zwyy_user, zwyy_time, zwyy_roomid, zwyy_devid, zwyy_devname, zwyy_priorityid, zwyy_priorityname, pushkey
    zwyy_user = zwyy_json['user']
    zwyy_time = zwyy_json['time']
    zwyy_roomid = jsonpath.jsonpath(zwyy_json, '$..roomid')
    zwyy_devid = jsonpath.jsonpath(zwyy_json, '$..devid')
    zwyy_devname = jsonpath.jsonpath(zwyy_json, '$..devname')
    zwyy_priorityid = zwyy_user[0]['priority_id']
    zwyy_priorityname = zwyy_user[0]['priority_name']
    pushkey = zwyy_json['pushkey']


# 获取和拼凑密钥，返回密钥和随机码
def get_nonceStr_publicKey(zwyy_con):
    url_nonceStr_publicKey = "https://zwyy.cidp.edu.cn/ic-web/login/publicKey"
    while True:
        try:
            con_nonceStr_publicKey = zwyy_con.get(url_nonceStr_publicKey, verify=False)
        except:
            continue
        finally:
            publicKey = '-----BEGIN PUBLIC KEY-----\n' + \
                        jsonpath.jsonpath(con_nonceStr_publicKey.json(), '$..publicKey')[
                            0] + '\n-----END PUBLIC KEY-----'
            nonceStr = jsonpath.jsonpath(con_nonceStr_publicKey.json(), '$..nonceStr')[0]
            return publicKey, nonceStr


# RSA加密密码，返回密文
def encrypt_password(zwyy_con, password):
    publicKey, nonceStr = get_nonceStr_publicKey(zwyy_con)
    rsaKey = RSA.importKey(publicKey)
    cipher = PKCS1_v1_5.new(rsaKey)
    r = str(password) + ";" + nonceStr
    encrypt_text = (base64.b64encode(cipher.encrypt(r.encode(encoding="utf-8")))).decode('utf-8')
    return encrypt_text


# 获取和解析验证码，返回验证码文本
def get_captcha(zwyy_con):
    con_get_captcha = None
    while True:
        try:
            url_get_captcha = f"https://zwyy.cidp.edu.cn/ic-web/captcha?id={int(time.time() * 1000)}"
            con_get_captcha = zwyy_con.get(url_get_captcha, verify=False, headers=headers)
        except:
            continue
        finally:
            captcha = ocr.classification(con_get_captcha.content)
            return captcha


# 登录，返回用户id和姓名
def get_login(zwyy_con, userid, password):
    n = 0
    while n <= 8:
        captcha = get_captcha(zwyy_con)
        pwd = encrypt_password(zwyy_con, password)
        url_login = "https://zwyy.cidp.edu.cn/ic-web/login/user"
        data = {"logonName": userid,
                "password": pwd,
                "captcha": captcha,
                "consoleType": 16}
        try:
            con_login = zwyy_con.post(url_login, json=data, verify=False, headers=headers)
        except:
            continue
        
        if "登录成功" in con_login.text:
            accNo = jsonpath.jsonpath(con_login.json(), '$..accNo')[0]
            trueName = jsonpath.jsonpath(con_login.json(), '$..trueName')[0]
            print("登录成功")
            return accNo, trueName
            pass
        elif "验证码错误" in con_login.text:
            n -= 1
        elif "账号或密码不正确" in con_login.text:
            _push(f"{userid}，账号或密码不正确")
            return int(00000000), int(00000000)
        elif n == 8:
            return int(00000000), int(00000000)
        n += 1


# 获取指定时间BeginTime-EndTime单个座位
def get_a_resv(zwyy_con, resvMember, resvDev, start_time, end_time, userid, password):
    BeginTime = tomorrow_date + " " + start_time  # 2022-11-01 13:05:00
    EndTime = tomorrow_date + " " + end_time  # 2022-11-01 14:50:00
    data = {"sysKind": 8, "appAccNo": int(resvMember), "memberKind": 1, "resvMember": [int(resvMember)],
            "resvBeginTime": BeginTime, "resvEndTime": EndTime, "testName": "", "captcha": "",
            "resvProperty": 0, "resvDev": [int(resvDev)], "memo": ""}
    try:
        con_nonceStr_publicKey = zwyy_con.post("https://zwyy.cidp.edu.cn/ic-web/reserve", json=data, verify=False,
                                               headers=headers)
    except:
        return "Get_Error"
    print(str(resvDev) + '，' + con_nonceStr_publicKey.text)
    
    if "新增成功" in con_nonceStr_publicKey.text:
        return "Success"
    elif "请在07:00之后" in con_nonceStr_publicKey.text:
        return "Get_Error"
    elif "该时间段内已被预约" in con_nonceStr_publicKey.text:
        return "Booked"
    elif "您有预约操作正在进行" in con_nonceStr_publicKey.text:
        return "Appointment_duplication"
    elif "用户未登录" in con_nonceStr_publicKey.text:
        while True:
            res = get_login(zwyy_con, userid, password)
            if res == int(00000000):
                return "User_Error"


# 获取指定时间BeginTime-EndTime内单个教室座位,返回两组数据
def get_all_resv(zwyy_con, resvMember, room_no, start_time, end_time, userid, password):
    dev_no = 0
    res_a = 00
    res_b = 00
    dev_id = zwyy_devid[room_no]
    dev_name = zwyy_devname[room_no]
    # 优选座位获取
    while True:
        priority_res = get_a_resv(zwyy_con, resvMember, zwyy_priorityid, start_time, end_time, userid, password)
        if priority_res == "Success":
            return zwyy_priorityid, zwyy_priorityname
        elif priority_res == "Appointment_duplication":
            continue
        elif priority_res == "Get_Error":
            continue
        elif priority_res == "Booked":
            break
        if int(time.strftime('%H%M', time.localtime(time.time()))) >= 701:
            break
    # 正常循环获取
    while dev_no < len(dev_id):
        if dev_id[dev_no] == zwyy_priorityid:
            dev_no += 1
            continue
        res = get_a_resv(zwyy_con, resvMember, dev_id[dev_no], start_time, end_time, userid, password)
        if res == "Get_Error":
            continue
        elif res == "Appointment_duplication":
            continue
        elif res == "Success":
            return dev_id[dev_no], dev_name[dev_no]
        elif res == "User_Error":
            break
        dev_no += 1
    return res_a, res_b


# 循环time_no时间段内获取多个教室
def get_all_room(zwyy_con, resvMember, time_no, userid, password):
    global all_res
    start_time = jsonpath.jsonpath(zwyy_time[time_no], '$..start_time')[0]
    end_time = jsonpath.jsonpath(zwyy_time[time_no], '$..end_time')[0]
    room_no = 0
    while room_no < len(zwyy_roomid):
        res_a, res_b = get_all_resv(zwyy_con, resvMember, room_no, start_time, end_time, userid, password)
        if "TY" in str(res_b):
            res = f"时间段为{start_time}到{end_time}，座位预约成功，位置为{res_b}\n"
            all_res += res
            return
        room_no += 1
        if res_b == 00 and room_no >= len(zwyy_roomid):
            res = f"时间段为{start_time}到{end_time}，座位预约失败\n"
            all_res += res
            return


def p_run():
    zwyy_con = requests.Session()  # 初始化requests
    # 进行登录
    to_print('进行登录……')
    user = zwyy_user[0]["id"]
    pwd = zwyy_user[0]["pwd"]
    userid, name = get_login(zwyy_con, user, pwd)
    if userid == int(00000000):
        _push("登录出现问题，请检查！")
        return
    # 确认时间，到点抢座位
    now_time = int(time.strftime('%H%M', time.localtime(time.time())))
    if now_time < 700:
        to_print("时间未到7:00，将不会进行座位预约，请等待时间到点，将每秒重新检查时间")
        while now_time < 700:
            to_print('现在时间是' + str(time.strftime('%H:%M:%S', time.localtime(time.time()))))
            time.sleep(1)
            now_time = int(time.strftime('%H%M', time.localtime(time.time())))
    to_print('现在时间是' + str(time.strftime('%H:%M:%S', time.localtime(time.time()))) + ",开始预约座位！\n")
    # 多线程获取座位
    global all_res
    all_res = f"姓名：{name},运行结果：\n"
    time_thread = 0
    while time_thread < len(zwyy_time):
        print(f"线程{time_thread}开始运行")
        t = threading.Thread(target=get_all_room, args=(zwyy_con, userid, time_thread, user, pwd,))
        t.start()
        t.join()
        time_thread += 1
    return "OK"
    # res = zwyy_th(userid, name, userid, pwd)


def main():
    os.system("cls")
    v_info()
    _push('现在时间是：' + str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))) + '脚本开始运行！')
    load_res = load_zwyy_json()  # 加载Json
    if load_res == "JsonNotFile":
        return
    p_run()
    _push(all_res)
    os.system("pause")


main()
