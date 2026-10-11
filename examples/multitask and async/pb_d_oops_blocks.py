# pybricks blocks file:{"blocks":{"languageVersion":0,"blocks":[{"type":"blockGlobalSetup","id":"bjK,wS1MYO7aiYkFSwd{","x":131,"y":65,"deletable":false,"next":{"block":{"type":"variables_setup_imported_function","id":"Wm0+EX,VzGRpj~7PT`v0","fields":{"FROM_MODULE":"uremote","VAR":{"id":"+5U[.|-%6?jUJB7e=VT("}},"next":{"block":{"type":"variables_setup_object_instance","id":"6ZUnIf2kAf:.RUg!t_b]","extraState":{"optionLevel":1},"fields":{"VAR":{"id":"y61wOD8V,a5;ez.:HGKl"},"CLASS_NAME":"uRemote"},"inputs":{"ARG0":{"shadow":{"type":"blockMathNumber","id":"rIaBxQNC:gF)iUR1zl;G","fields":{"NUM":0}},"block":{"type":"blockTextLiteral","id":"x3wr*4AtQ(Tg_23{[)4*","fields":{"TEXT":"A"}}}}}}}}},{"type":"blockGlobalStart","id":"3tJe|AWl0baN(wH9a$@.","x":131,"y":224,"deletable":false,"next":{"block":{"type":"blockPrint","id":"j,,T}?rBkaW$1v?olp4p","extraState":{"optionLevel":0},"inputs":{"TEXT0":{"shadow":{"type":"text","id":"!x5.0YiWya^`(y)yO5B8","fields":{"TEXT":"Hello, Pybricks!"}}}}}}},{"type":"blockGlobalStart","id":"-;D],Z!Y`$Ed8!e2|m[A","x":132,"y":348,"next":{"block":{"type":"blockPrint","id":".6p_-EEC(6nn)?TTD}-D","extraState":{"optionLevel":0},"inputs":{"TEXT0":{"shadow":{"type":"text","id":"jqN49U4j+XfPVv_KvMkY","fields":{"TEXT":"abc"}},"block":{"type":"blockObjectInstanceCallValue","id":"L%LRv[D0.wkP(AY|nz(-","extraState":{"optionLevel":3},"fields":{"CALL_TYPE":"CLASS_CALL_METHOD_SYNC","METHOD":"call"},"inputs":{"VAR":{"shadow":{"type":"variables_get_object_instance","id":"p8ngJv[(`S6aB^?2aWwR","fields":{"VAR":{"id":"y61wOD8V,a5;ez.:HGKl","name":"ur","type":"ObjectInstance"}}}},"ARG0":{"shadow":{"type":"blockMathNumber","id":"jr/%Meh8MK8e49lG+Z(H","fields":{"NUM":0}},"block":{"type":"blockTextLiteral","id":"TJlR$-GjmWP`We/smqfq","fields":{"TEXT":"add"}}},"ARG1":{"shadow":{"type":"blockMathNumber","id":"fv6pM1Ylg$Wqc#6}4^NA","fields":{"NUM":20}}},"ARG2":{"shadow":{"type":"blockMathNumber","id":"?H](q!DLYt|#u:YvJ{.m","fields":{"NUM":22}}}}}}}}}}]},"variables":[{"name":"red","id":"T0P+K({^f{93dN)%nMK8","type":"ColorDef"},{"name":"orange","id":"~eMK6_#LqEEEO/gEsR*Q","type":"ColorDef"},{"name":"yellow","id":"^z/xq)jtrAe=#OC410*Z","type":"ColorDef"},{"name":"green","id":"x-]JKX]{nUWiQ[j~$]n,","type":"ColorDef"},{"name":"cyan","id":"(bay}0LkV,^:gq`8_hJ!","type":"ColorDef"},{"name":"blue","id":"oB1H2O`jaW{W6Kp(%HO/","type":"ColorDef"},{"name":"violet","id":"GU8^bRT1[(G{n%Cd#TSJ","type":"ColorDef"},{"name":"magenta","id":".02,T=eu}HfPh~.O%F{z","type":"ColorDef"},{"name":"white","id":"GbbY(qk$vU@c|u$vlXsx","type":"ColorDef"},{"name":"none","id":"jq3RB*k#3ssb6.I[:9{)","type":"ColorDef"},{"name":"uRemote","id":"+5U[.|-%6?jUJB7e=VT(","type":"FunctionImported"},{"name":"ur","id":"y61wOD8V,a5;ez.:HGKl","type":"ObjectInstance"}],"info":{"type":"pybricks","version":"2.0.0"},"workspaceOptions":{"scrollX":104.99999999999989,"scrollY":0,"scale":1}}
from pybricks.tools import multitask, run_task, wait

from uremote import uRemote

# Set up.
ur = uRemote('A')

async def main1():
    print('Hello, Pybricks!')

async def main2():
    print(ur.call('add', 20, 22))


async def main():
    await multitask(main1(), main2())

run_task(main())