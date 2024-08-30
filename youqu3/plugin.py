import os
import re

from _pytest.mark import Mark
from funnylog2 import logger

from youqu3 import setting
from youqu3 import skipif

FLAG_FEEL = "=" * 10


def add_mark(item, name: str = "", args: tuple = (), kwargs: dict = None):
    item.own_markers.append(Mark(name=name, args=args, kwargs=kwargs))


def walk_apps(walk_dir):
    """walk apps"""
    no_youqu_mark = {}
    csv_path_dict = {}
    for root, _, files in os.walk(walk_dir):
        if "NOYOUQUMARK" in files and not no_youqu_mark.get(root):
            no_youqu_mark[root] = True
            continue
        for file in files:
            if file.endswith(".csv") and file != "case_list.csv":
                csv_path_dict[os.path.splitext(file)[0]] = f"{root}/{file}"
    return csv_path_dict, no_youqu_mark


def pytest_addoption(parser):
    parser.addoption("--noskip", action="store", default="", help="skip-xxx标签不生效")
    parser.addoption("--ifixed", action="store", default="", help="fixed-xxx标签不生效")


def pytest_sessionstart(session):
    logger("DEBUG")


def pytest_collection_modifyitems(session):
    csv_path_dict, no_youqu_mark = walk_apps(session.startdir)

    if not csv_path_dict:
        return

    containers = {}

    skip_index = fixed_index = removed_index = None

    for item in session.items[::-1]:
        item.name = item.name.encode("utf-8").decode("unicode_escape")
        item._nodeid = item.nodeid.encode("utf-8").decode("unicode_escape")

        if no_youqu_mark:
            continue_flag = False
            for app_abspath in no_youqu_mark:
                if app_abspath in item.fspath.strpath:
                    continue_flag = True
                    break
            if continue_flag:
                continue

        try:
            csv_name, _id = re.findall(r"test_(.*?)_(\d+)", item.name)[0]
            _case_name, _case_id = re.findall(r"test_(.*?)_(\d+)", item.fspath.purebasename)[0]
            if _id != _case_id:
                raise ValueError
            if _case_name != csv_name:
                raise FileNotFoundError
        except IndexError:
            skip_text = f"用例函数名称缺少用例id:[{item.nodeid}]"
            logger.error(skip_text)
            add_mark(item, setting.ConfStr.SKIP.value, (skip_text,), {})
        except ValueError:
            skip_text = f"用例py文件的id与用例函数的id不一致:[{item.nodeid}]"
            logger.error(skip_text)
            add_mark(item, setting.ConfStr.SKIP.value, (skip_text,), {})
        except FileNotFoundError:
            logger.error(f"用例py文件的名称与用例函数的名称不一致:[{item.nodeid}]")
            session.items.remove(item)
        else:
            csv_path = csv_path_dict.get(csv_name)
            if not csv_path:
                if "asan" not in csv_name:
                    logger.error(f"{csv_name}.csv 文件不存在!")
                continue

            if not containers.get(csv_path):
                with open(csv_path, "r", encoding="utf-8") as _f:
                    txt_list = _f.readlines()
                if not txt_list:
                    continue
                # 通过csv的表头找到对应的索引（排除ID列的索引）
                for index, title in enumerate(txt_list[0].strip().split(",")):
                    if title.strip() == setting.FixedCsvTitle.skip_reason.value:
                        skip_index = index - 1
                    elif title.strip() == setting.FixedCsvTitle.fixed.value:
                        fixed_index = index - 1
                    elif title.strip() == setting.FixedCsvTitle.removed.value:
                        removed_index = index - 1

                taglines = [txt.strip().split(",") for txt in txt_list[1:]]
                id_tags_dict = {f"{int(i[0]):0>3}": i[1:] for i in taglines if i[0]}

                # 每个csv文件单独管理一套index
                containers[csv_path] = id_tags_dict
                containers[csv_path][setting.ConfStr.SKIP_INDEX.value] = skip_index
                containers[csv_path][setting.ConfStr.FIXED_INDEX.value] = fixed_index
                containers[csv_path][setting.ConfStr.REMOVED_INDEX.value] = removed_index
                # 将index重置
                skip_index = fixed_index = removed_index = None

            tags = containers.get(csv_path).get(_id)
            if tags:
                try:
                    if containers[csv_path][setting.ConfStr.REMOVED_INDEX.value] is not None and tags[
                        containers[csv_path][setting.ConfStr.REMOVED_INDEX.value]
                    ].strip('"').startswith(f"{setting.ConfStr.REMOVED.value}-"):
                        session.items.remove(item)
                        continue
                except IndexError as exc:
                    logger.error(
                        f"\ncsv_path:\t{csv_path}\ntags:\t{tags}\n"
                        f"error_tag_index:\t{containers[csv_path][setting.ConfStr.REMOVED_INDEX.value]}"
                    )
                    raise IndexError from exc
                for index, tag in enumerate(tags):
                    if tag:
                        tag = tag.strip('"')
                        # 先处理“跳过原因”列
                        if index == containers[csv_path][setting.ConfStr.SKIP_INDEX.value]:
                            # 标签是以 “skip-” 开头, noskip 用于解除所有的skip
                            if not session.config.option.noskip and tag.startswith(
                                    f"{setting.ConfStr.SKIP.value}-"
                            ):
                                # 标签以 “fixed-” 开头, ifixed表示ignore fixed, 用于忽略所有的fixed
                                # 1. 不给ifixed参数时，只要标记了fixed的用例，即使标记了skip-，也会执行；
                                # 2. 给ifixed 参数时(--ifixed yes)，fixed不生效，仅通过skip跳过用例；
                                try:
                                    if (
                                            not session.config.option.ifixed
                                            and containers[csv_path][setting.ConfStr.FIXED_INDEX.value]
                                            is not None
                                            and tags[containers[csv_path][setting.ConfStr.FIXED_INDEX.value]]
                                            .strip('"')
                                            .startswith(f"{setting.ConfStr.FIXED.value}-")
                                    ):
                                        continue
                                except IndexError:
                                    # 如果访问越界，说明这行没有fixed标签或者标签写错位置了，所以正常跳过
                                    pass
                                add_mark(item, setting.ConfStr.SKIP.value, (tag,), {})
                            elif (
                                    not session.config.option.noskip
                                    and f"{setting.ConfStr.SKIPIF.value}_" in tag
                            ):
                                tag_list = tag.split("&&")
                                for _tag in tag_list:
                                    skip_method, param = _tag.strip(" ").split("-", maxsplit=1)
                                    if hasattr(skipif, skip_method):
                                        skip_result = getattr(skipif, skip_method)(param)
                                        add_mark(
                                            item,
                                            setting.ConfStr.SKIPIF.value,
                                            (skip_result,),
                                            {"reason": _tag},
                                        )
                                    else:
                                        logger.error(
                                            f"未找到判断是否跳过的自定义方法 <{skip_method}>"
                                        )
                                        add_mark(
                                            item,
                                            setting.ConfStr.SKIP.value,
                                            (f"未找到判断是否跳过的自定义方法 <{skip_method}>",),
                                            {},
                                        )
                        else:  # 非跳过列

                            # 处理其他自定义标签
                            try:
                                mark_title = txt_list[0].strip().split(",")[index + 1]
                            except IndexError:
                                # 如果写了标签，但是没有对应的表头
                                mark_title = ""
                            add_mark(item, tag, (mark_title,), {})

            else:
                if session.config.option.allure_report_dir:
                    # 批量执行时，不执行没有ID的用例。
                    logger.error(f"<{item.name}> csv文件中未标记,强制跳过")
                    session.items.remove(item)

    print()  # 处理日志换行


def pytest_collection_finish(session):
    session.item_count = len(session.items)
    _items = session.items[:]
    is_skiped_case = False
    for item in _items[::-1]:
        for mark in item.own_markers:
            if mark.name == setting.ConfStr.SKIP.value:
                is_skiped_case = True
                try:
                    _items.remove(item)
                except ValueError:
                    ...
            elif mark.name == setting.ConfStr.SKIPIF.value and mark.args == (True,):
                is_skiped_case = True
                try:
                    _items.remove(item)
                except ValueError:
                    ...
    print(
        f"用例收集数量:\t{session.item_count} "
        f"{f'(剔除跳过: {len(_items)})' if is_skiped_case else ''}"
    )
    print(
        f"用例文件数量:\t{len(set([item.fspath for item in session.items]))} "
        f"{f'(剔除跳过: {len(set([item.fspath for item in _items]))})' if is_skiped_case else ''}"
    )


def pytest_runtest_setup(item):
    print()
    LN = "\n"
    current_item_count = f"[{item.session.items.index(item) + 1}/{item.session.item_count}] "
    try:
        current_item_percent = "{:.0f}%".format(
            int(item.session.items.index(item) + 1) / int(item.session.item_count) * 100
        )
    except:
        current_item_percent = ""
    try:
        rerun_text = f" | <重跑第{item.execution_count - 1}次>" if item.execution_count > 1 else ""
    except AttributeError:
        rerun_text = ""
    logger.info(
        f"{LN}{FLAG_FEEL} {item.function.__name__} | "
        f"{str(item.function.__doc__).replace(LN, '').replace('    ', '')}{rerun_text} "
        f"{FLAG_FEEL} {current_item_count} {current_item_percent}"
    )


def pytest_runtest_call(item):
    logger.info(f"{FLAG_FEEL} case body {FLAG_FEEL}")


def pytest_runtest_teardown(item):
    logger.info(f"{FLAG_FEEL} teardown {FLAG_FEEL}")
