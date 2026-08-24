# 法律信息爬虫

程序使用 `requests + BeautifulSoup` 访问官方公开网页，按发布日期过滤并保存标题、日期、来源和链接。当前法院模式包含：

- 山东高法
- 上海一中法院（上海一中院）
- 上海二中法院（上海二中院）
- 苏州中级法院（苏州中院）
- 深圳中级人民法院

## 安装

```powershell
python -m pip install -r requirements.txt
```

## 运行

爬取最近 31 天的五个法院案例：

```powershell
python run.py 31 --courts-only --no-filter
```

`--sdcourt-only` 仍可使用，但现在作为兼容别名，也会爬取上述五个法院。只爬取山东高法可在 Python 中调用 `LawCrawler.crawl_sdcourt()`。

也可以指定包含首尾日期的区间：

```powershell
python run.py --start 2026-08-01 --end 2026-08-24 --courts-only --no-filter
```

结果写入项目目录的 `result.txt`。默认只保存公开页面的元数据，不绕过登录、验证码或其他访问控制。法院网站的栏目路径可能调整，可在 `config.py` 的 `COURT_SITES` 中更新入口 URL、关键词和遍历上限。
