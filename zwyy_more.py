#  Copyright (c) 2022. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.

import json
import re
import sys
import threading
import time

import jsonpath
import requests

users = 0
if len(sys.argv) == 2:
    users = int(sys.argv[1])

zwyy_times = int(time.time() * 1000)
zwyy_day = str(time.strftime('%Y-%m-%d', time.localtime(time.time() + 86400)))

zwyy_json = json.load(open('zwyy_json.json', 'r', encoding='utf-8'))  # 使用cron运行请写完整路径
zwyy_user = jsonpath.jsonpath(zwyy_json, '$..user')[0]
if users > len(zwyy_user) - 1:
    users = 0

zwyy_time = jsonpath.jsonpath(zwyy_json, '$..time')[0]
zwyy_roomid = jsonpath.jsonpath(zwyy_json, '$..roomid')
zwyy_devid = jsonpath.jsonpath(zwyy_json, '$..devid')
zwyy_devname = jsonpath.jsonpath(zwyy_json, '$..devname')
zwyy_pushkey = jsonpath.jsonpath(zwyy_json, '$..pushkey')[0]
zwyy_priorityid = (jsonpath.jsonpath(zwyy_user[users], '$..priority_id'))[0]
zwyy_priorityname = (jsonpath.jsonpath(zwyy_user[users], '$..priority_name'))[0]

zwyy_headers = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/104.0.0.0 Safari/537.36"}

zwyy_con = requests.Session()


def login(userid, pwd):
    global res
    url_login = f"https://zwyy.cidp.edu.cn/ClientWeb/pro/ajax/login.aspx?id={userid}&pwd={pwd}&act=login"
    zwyy_login = zwyy_con.get(url_login, headers=zwyy_headers)
    if '个人预约制度' in zwyy_login.text:
        res = jsonpath.jsonpath(zwyy_login.json(), '$..name')[0]
    if '输入有误' in zwyy_login.text:
        res = "Login Error!"
    return res


def get_room_info(roomid, info):
    url_get_rsv_sta = "https://zwyy.cidp.edu.cn/ClientWeb/pro/ajax/device.aspx?byType=devcls&" \
                      "classkind=8&display=fp&md=d&room_id={}&purpose=&selectOpenAty=&" \
                      "cld_name=default&date={}&fr_start=08:00&fr_end=22:00&act=get_rsv_sta&_={}".format(roomid,
                                                                                                         zwyy_day,
                                                                                                         zwyy_times)
    zwyy_get_room = zwyy_con.get(url_get_rsv_sta, headers=zwyy_headers)
    res = jsonpath.jsonpath(zwyy_get_room.json(), f'$..{info}')
    return res


def pushdeer(text):
    push_url = f"{jsonpath.jsonpath(zwyy_json, '$..push_url')[0]}pushkey={zwyy_pushkey[users]}&text={text}"
    requests.post(push_url)
    pass


def set_resv(devid, devname, name, start_time, end_time):
    url_set_resv = "https://zwyy.cidp.edu.cn/ClientWeb/pro/ajax/reserve.aspx?dialogid=" \
                   "&dev_id={dev}" \
                   "&lab_id=&kind_id=&room_id=&type=dev&prop=&test_id=&term=&number=&classkind=&test_name=" \
                   "&start={day}+{start_time}&end={day}+{end_time}" \
                   "&start_time={start_time_n}&end_time={end_time_n}" \
                   "&up_file=&memo=&act=set_resv&_={timestamp}".format(dev=devid, day=zwyy_day, start_time=start_time,
                                                                       end_time=end_time,
                                                                       start_time_n=re.sub(':', '', start_time),
                                                                       end_time_n=re.sub(':', '', end_time),
                                                                       timestamp=zwyy_times)
    zwyy_set_resv = zwyy_con.get(url_set_resv, headers=zwyy_headers)
    res = (jsonpath.jsonpath(zwyy_set_resv.json(), '$..msg'))[0]
    if '操作成功' in res:
        if devid == zwyy_priorityid:
            pushdeer(
                f"姓名：{name}，优先预约成功，位置为{devname}。时间段为{start_time}到{end_time}")
        else:
            pushdeer(
                f"姓名：{name}，循环预约成功，位置为{devname}。时间段为{start_time}到{end_time}")
    return res


def try_set_resv(userid, pwd, name, room_no, start_time, end_time):
    dev_id = zwyy_devid[room_no]
    dev_name = zwyy_devname[room_no]
    n = 0
    res = 1
    used_priority = 0
    while n < len(dev_id):
        if used_priority == 0:
            priority_res = set_resv(zwyy_priorityid, zwyy_priorityname, name, start_time, end_time)
            if 'ERRMSG_RESV_CONFLICT' in priority_res:
                used_priority = 1
            if '操作成功' in priority_res:
                res = 0
                break
            if '未登录' in priority_res:
                name = login(userid, pwd)
                continue
            if '请在7:00之后' in priority_res:
                time.sleep(0.5)
                continue
        if dev_id[n] == zwyy_priorityid:
            n += 1
        t_res = set_resv(dev_id[n], dev_name[n], name, start_time, end_time)
        if '未登录' in t_res:
            name = login(userid, pwd)
            continue
        if '操作成功' in t_res:
            res = 0
            break
        n += 1
    return res


def run_zwyy(userid, pwd, time_no):
    login_res = login(userid, pwd)
    start_time = jsonpath.jsonpath(zwyy_time[time_no], '$..start_time')[0]
    end_time = jsonpath.jsonpath(zwyy_time[time_no], '$..end_time')[0]
    if login_res == 1 or login_res == "Login Error!":
        pushdeer(f"学号：{userid}，登录失败")
        sys.exit(1)
    room_no = 0
    res = 1
    while room_no < len(zwyy_roomid):
        res = try_set_resv(userid, pwd, login_res, room_no, start_time, end_time)
        room_no += 1
        if res == 0:
            break
    if res == 1:
        res = "姓名：{}，日期：{}，{}至{}时间段预约座位失败 ".format(login_res, zwyy_day, start_time, end_time)
        pushdeer(res)
    pass


def zwyy_th(userid, pwd):
    time_thread = 0
    while time_thread < len(zwyy_time):
        threading.Thread(target=run_zwyy, args=(userid, pwd, time_thread,)).start()
        time_thread += 1
    pass


def main():
    pushdeer(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())) + ' 开始')
    zwyy_th((jsonpath.jsonpath(zwyy_user[users], '$..id'))[0], (jsonpath.jsonpath(zwyy_user[users], '$..pwd'))[0])
    pass


if len(sys.argv) == 3:
    res = get_room_info(sys.argv[1], sys.argv[2])
    print(res)
    sys.exit(0)

main()
