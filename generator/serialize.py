import json
def dumps(d):
    ph = {}
    d2 = dict(d); items = []
    for i, r in enumerate(d['leki']):
        k = "@@LEK%d@@" % i; ph[k] = json.dumps(r, ensure_ascii=False, separators=(',', ':')); items.append(k)
    d2['leki'] = items
    s = json.dumps(d2, ensure_ascii=False, indent=1)
    for k, v in ph.items(): s = s.replace('"%s"' % k, v, 1)
    return s + '\n'
