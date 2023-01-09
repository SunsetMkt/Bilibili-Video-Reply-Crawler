#!/usr/bin/env python3
# Python爬虫获取Bilibili视频评论
# Source: https://zhuanlan.zhihu.com/p/275603349
# Modified
# 注：
# 这里使用的API可能未更新，虽然能用，但是可能会有问题；
# IP属地信息仅会在有有效Cookies时才会包含在请求结果中，暂不支持；
# 由于哔哩哔哩API不是设计用于爬虫的，每次执行结果不可复现，也不保证保存所有评论；
# 爬取评论数和哔哩哔哩网页显示总数可能不一致，无法解决，可能由于审查/系统设计问题导致部分评论被隐藏；
# 专栏的type=12，oid 为专栏 cvid，已做支持；
import argparse
import hashlib
import re
import time

import requests
import urllib3

urllib3.disable_warnings()

hd = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.76",
}


def get_oid(BV_CODE: str) -> str:
    # oid 为稿件 avid https://github.com/SocialSisterYi/bilibili-API-collect
    # Source: https://www.zhihu.com/question/381784377/answer/1099438784
    # 注：这里请求 https://api.bilibili.com/x/web-interface/view?bvid=1yv411r7WH 也可以拿到 aid

    global vidType

    table = 'fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF'
    tr = {}
    for i in range(58):
        tr[table[i]] = i
    s = [11, 10, 3, 8, 4, 6]
    xor = 177451812
    add = 8728348608

    def dec(x):
        r = 0
        for i in range(6):
            r += tr[x[s[i]]]*58**i
        return (r-add) ^ xor

    def enc(x):
        x = (x ^ xor)+add
        r = list('BV1  4 1 7  ')
        for i in range(6):
            r[s[i]] = table[x//58**i % 58]
        return ''.join(r)
    if BV_CODE.startswith('BV'):
        vidType = 'bv'
        return str(dec(BV_CODE))
    elif BV_CODE.startswith('av'):
        vidType = 'av'
        return str(BV_CODE[2:])
    elif BV_CODE.startswith('cv'):
        vidType = 'cv'
        return str(BV_CODE[2:])


def get_data(page: int, oid: str):
    global vidType

    time.sleep(sleep_time)  # 减少访问频率，防止IP封禁
    if vidType == 'cv':
        api_url = f"https://api.bilibili.com/x/v2/reply?jsonp=jsonp&pn={page}&type=12&oid={oid}&sort=2&_={int(time.time())}"
    else:
        api_url = f"https://api.bilibili.com/x/v2/reply?jsonp=jsonp&pn={page}&type=1&oid={oid}&sort=2&_={int(time.time())}"
    print(f'正在处理:{api_url}')  # 由于需要减缓访问频率，防止IP封禁，打印访问网址以查看访问进程
    r = requests.get(api_url, headers=hd, verify=False)
    r.raise_for_status()

    if args.verbose:
        print(r.json())

    return r.json()['data']['replies'], r.json()['data']['page']['count']


def get_folded_reply(page: int, oid: str, root: int):
    global vidType

    time.sleep(sleep_time)  # 减少访问频率，防止IP封禁
    if vidType == 'cv':
        url = f'https://api.bilibili.com/x/v2/reply/reply?jsonp=jsonp&pn={page}&type=12&oid={oid}&ps=10&root={root}&_={int(time.time())}'
    else:
        url = f'https://api.bilibili.com/x/v2/reply/reply?jsonp=jsonp&pn={page}&type=1&oid={oid}&ps=10&root={root}&_={int(time.time())}'
    print(f'正在处理:{url}')  # 由于需要减缓访问频率，防止IP封禁，打印访问网址以查看访问进程
    r = requests.get(url, headers=hd, verify=False)
    r.raise_for_status()

    if args.verbose:
        print(r.json())

    return r.json()['data']


def re_reply2(temp, root):
    _ = []
    for item in temp:
        if item[2] == root:
            _.append((item[1], 'FIRST'))
            continue
        for item2 in temp:
            if item[2] == item2[1]:
                _.append((item[1], item2[1]))
                break
        else:  # 回复对象被删除
            _.append((item[1], None))
    return _


def loop_folded_reply(root: int, rcount: int):
    temp = []
    temp2 = {}
    end_page = (rcount - 1) // 10 + 1 if (rcount -
                                          1) // 10 + 1 <= pages2 else pages2
    for page in range(1, end_page + 1):
        data = get_folded_reply(page, oid=oid, root=root)
        if not data['replies']:
            continue
        for item in data['replies']:
            mid = item['mid']
            rpid = item['rpid']
            parent = item['parent']
            dialog = item['dialog']
            rcount = item['rcount']
            like = item['like']
            ctime = item['ctime']
            name = item['member']['uname']

            # message = item['content']['message']
            if args.do_not_replace:
                message = item['content']['message']
                message = message.replace('\n', '\\n')
                message = message.replace('\t', '\\t')
            else:
                message = re.sub(r'\t|\n|回复 @.*? :', '',
                                 item['content']['message'])

            if args.verbose:
                print(dialog, rpid, parent, name, message)

            temp.append([dialog, rpid, parent, name, message])
            temp2[rpid] = [mid, message, name, like, ctime]
        # else:
        #     break
    pointer = re_reply2(temp, root)

    def loop(pid, tab):
        # 用于递归查找单指
        for item in pointer:
            if pid == item[1]:
                mid, message, name, like, ctime = temp2[item[0]]
                f.write(
                    '|\t' * tab + f'|->\t点赞：{like}\t评论："{message}"\tUSER：{name}(UID：{mid})\t{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ctime))}\n')
                loop(item[0], tab + 1)

    for rpid in [i for i, j in pointer if j == 'FIRST']:
        mid, message, name, like, ctime = temp2[rpid]
        f.write(
            f'|\t|->\t点赞：{like}\t评论："{message}"\tUSER：{name}(UID：{mid})\t{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ctime))}\n')
        loop(rpid, tab=1)

    for ii, rpid in enumerate([i for i, j in pointer if not j]):
        if ii == 0:
            f.write(f'|\t|->\t评论已被删除\n')
        mid, message, name, like, ctime = temp2[rpid]
        f.write(
            f'|\t|\t|->\t点赞：{like}\t评论："{message}"\tUSER：{name}(UID：{mid})\t{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ctime))}\n')
        loop(rpid, tab=3)


def get_reply(data, tab=0):
    if not data:
        return
    for item in data:
        mid = item['mid']
        rpid = item['rpid']
        count = item['count']
        rcount = item['rcount']
        like = item['like']
        ctime = item['ctime']
        name = item['member']['uname']

        # 下面的正则的替代方案
        if args.do_not_replace:
            message = item['content']['message']
            message = message.replace('\n', '\\n')
            message = message.replace('\t', '\\t')
        else:
            message = re.sub(r'\t|\n|回复 @.*? :', '',
                             item['content']['message'])  # 这会移除\t \n 和 回复 @xxx :

        f.write(
            '|\t' * tab + f'|->\t点赞：{like}\t评论："{message}"\tUSER：{name}(UID：{mid})\t{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ctime))}\n')
        print(f'处理评论:UID-{mid}\tUSER-{name}\t点赞-{like}')
        if 0 < rcount <= 3:
            get_reply(item['replies'], tab=1)
        elif rcount > 3:
            loop_folded_reply(root=rpid, rcount=rcount)


if __name__ == '__main__':
    # ArgumentParser
    parser = argparse.ArgumentParser(description='Bilibili视频评论爬虫')
    parser.add_argument('-v', '--video', type=str,
                        help='视频BV号，格式为BVxxxxxx，或者av号，格式为avxxxxxx，或者cv号，格式为cvxxxxxx')
    parser.add_argument('-p', '--pages', type=int, help='爬取评论页数')
    parser.add_argument('-r', '--replies', type=int, help='爬取评论回复页数')
    parser.add_argument('-o', '--output', type=str, help='输出文件名')
    parser.add_argument('-V', '--verbose', action='store_true', help='显示详细信息')
    parser.add_argument('--do-not-replace',
                        action='store_true', help='不删除回复中的换行和回复提示')
    args = parser.parse_args()

    maxMode = False  # 阻止盲目遍历
    vidType = 'bv'  # 视频类型，bv或cv，默认bv

    if args.video:
        BV_CODE = args.video
        if args.pages:
            pages1 = args.pages
        else:
            pages1 = 100000000
            print('未指定爬取页数，默认爬取100000000页评论，直到API返回空内容')
            maxMode = True  # 阻止盲目遍历
        if args.replies:
            pages2 = args.replies
        else:
            pages2 = 100000000
            print('未指定爬取回复页数，默认爬取100000000页评论回复')
    else:
        BV_CODE = str(input('请输入爬取评论的视频BV号：'))  # "BV1yv411r7WH"  # 视频的BV号
        pages1 = int(input('请输入爬取“视频评论”的页数（每页20条），推荐10：'))
        pages2 = int(input('请输入爬取“评论回复”的页数（每页10条），推荐03：'))
    sleep_time = 2.1  # 访问网页间隔，防止IP被禁，若运行程序后出现无法访问网页版BILIBILI评论区的现象，等待2小时即可~_~!
    oid = get_oid(BV_CODE)

    if args.output:
        fn = args.output
    else:
        fn = f'{BV_CODE}-{time.strftime("%Y%m%d-%H%M%S")}.txt'

    f = open(fn, 'w', encoding='utf-8')

    f.write(f'{BV_CODE}-{time.strftime("%Y%m%d-%H%M%S")}\n')

    page = 1
    while True:
        try:
            data, reply_num = get_data(page, oid)

            if args.verbose:
                print(data)
                print(reply_num)

            get_reply(data)  # 遍历所有回复

            if maxMode:
                if data == None:
                    print('API返回空内容，停止遍历')
                    print(page)
                    break  # 阻止盲目遍历，不知道能否按预期工作，似乎可以

            end_page = reply_num // 20 + 1 if reply_num // 20 + 1 <= pages1 else pages1
            if page == end_page:
                break
            page += 1

            # 渐进保存文件
            f.flush()

        except Exception as e:
            print('ERROR:', e)
            import traceback
            traceback.print_exc()
            # Save traceback to file
            f.write('\n' + str(traceback.format_exc()) + '\n')
            f.close()
            print('保存文件 退出循环 结束')
            break
    f.close()
    print('成功结束')

    if args.verbose:
        # print f content
        with open(fn, 'r', encoding='utf-8') as f:
            print(f.read())

    # Generate sha256sum
    print('生成sha256sum')
    with open(fn, 'rb') as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    # with open(fn + '.sha256sum', 'w', encoding='utf-8') as f:
    #     f.write(sha256)
    print('sha256sum:', sha256)
