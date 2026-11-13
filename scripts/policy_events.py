"""Validate public-only official evidence and render reviewed event updates.

No GitHub write, merge, publish, credential or private-briefing access lives here.
A domain/quotation check is necessary but cannot establish semantic truth: an
editor must independently read each source and review every proposed draft PR.
"""
import argparse
import copy
from datetime import date
import html
from html.parser import HTMLParser
import json
import re
from pathlib import Path
import subprocess
import tempfile
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'data/policy-events.json'
PAYLOAD = re.compile(r'(const data=)(.*?)(;\nfunction drawRange)', re.S)
OFFICIAL_HOSTS = {
    'Diet': {'www.shugiin.go.jp', 'www.sangiin.go.jp'},
    'MOF': {'www.mof.go.jp'}, 'BOJ': {'www.boj.or.jp'},
    'Cabinet Office': {'www.cao.go.jp', 'www5.cao.go.jp'},
    'Cabinet Secretariat': {'www.cas.go.jp'},
    'Prime Minister': {'japan.kantei.go.jp', 'www.kantei.go.jp'},
    'FED': {'www.federalreserve.gov'},
    'BLS': {'www.bls.gov'},
}
COLORS = {'expansionary': '#15803d', 'contractionary': '#c62828',
          'mixed': '#b77908', 'neutral': '#76818c', 'fx': '#8064a2'}
CATEGORIES = {'Fiscal', 'BoJ', 'FX intervention', 'Fed', 'U.S. CPI'}
STAGES = {'proposal', 'announcement', 'decision', 'enactment', 'implementation',
          'operation', 'disclosure', 'communication'}
EVENT_FIELDS = {'id', 'issuer', 'category', 'stage', 'event_date', 'date_basis',
                'disclosure_date', 'verified_on', 'title', 'summary', 'classification',
                'direction', 'caveat', 'sources'}
OPTIONAL_FIELDS = {'legacy_id', 'effective_date', 'plot_date'}
SOURCE_FIELDS = {'url', 'title', 'published_date', 'quotes'}
PRIVATE_PATTERNS = re.compile(r'(?:chatgpt\.com/(?:c|g)/|sandbox:|/mnt/data/|'
                              r'private briefing|briefing text|api[_ -]?key|'
                              r'BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY)', re.I)
MANAGED_START = '<!-- verified-policy-updates:start -->'
MANAGED_END = '<!-- verified-policy-updates:end -->'


def text(value, field, limit=2400):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'Invalid {field}')
    if any(ord(c) < 32 and c not in '\n\t' for c in value):
        raise ValueError(f'Control character in {field}')
    if '<' in value or '>' in value or PRIVATE_PATTERNS.search(value):
        raise ValueError(f'Non-public or markup content in {field}')
    return value


def iso(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Dates must be ISO YYYY-MM-DD')
    return date.fromisoformat(value)


def official_url(url, issuer):
    text(url, 'source URL', 1000)
    u = urlsplit(url)
    if (u.scheme != 'https' or u.hostname not in OFFICIAL_HOSTS[issuer]
            or u.username or u.password or u.port not in (None, 443)
            or u.query or u.fragment or not u.path or u.path == '/'):
        raise ValueError('Source must be a direct HTTPS page on the named official host')
    return url


def identity(event):
    return (event['issuer'], event['category'], event['event_date'], event['stage'])


def validate(registry, today=None):
    today = today or date.today()
    if not isinstance(registry, dict) or set(registry) != {'schema_version', 'events'}:
        raise ValueError('Registry permits only schema_version and public events')
    if type(registry['schema_version']) is not int or registry['schema_version'] != 1:
        raise ValueError('Unsupported schema version')
    if not isinstance(registry['events'], list) or len(registry['events']) > 1000:
        raise ValueError('Invalid event list')
    ids, identities, legacy, marker_ids = set(), set(), set(), set()
    for event in registry['events']:
        if not isinstance(event, dict) or not EVENT_FIELDS <= set(event) or set(event) - EVENT_FIELDS - OPTIONAL_FIELDS:
            raise ValueError('Unexpected or missing event fields; private inputs are forbidden')
        for key in EVENT_FIELDS - {'sources'} | (OPTIONAL_FIELDS & set(event)):
            text(event[key], key)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{2,79}', event['id']):
            raise ValueError('Invalid event ID')
        if event['issuer'] not in OFFICIAL_HOSTS or event['category'] not in CATEGORIES:
            raise ValueError('Unrecognized issuer or category')
        if event['stage'] not in STAGES or event['direction'] not in COLORS:
            raise ValueError('Unrecognized stage or direction')
        if (event['category'] == 'FX intervention') != (event['direction'] == 'fx'):
            raise ValueError('FX classification must use FX direction')
        if event['category'] == 'BoJ' and event['issuer'] != 'BOJ':
            raise ValueError('BoJ event must be sourced to BOJ')
        if event['category'] == 'FX intervention' and event['issuer'] != 'MOF':
            raise ValueError('Japanese intervention must be sourced to MOF')
        if event['category'] == 'Fed' and event['issuer'] != 'FED':
            raise ValueError('Fed events require an official Federal Reserve source')
        if event['category'] == 'U.S. CPI' and event['issuer'] != 'BLS':
            raise ValueError('U.S. CPI events require an official BLS source')
        if event['issuer'] in ('FED', 'BLS') and event['category'] not in ('Fed', 'U.S. CPI'):
            raise ValueError('Global issuer/category mismatch')
        when, disclosed, checked = map(iso, [event['event_date'], event['disclosure_date'], event['verified_on']])
        if not when <= disclosed <= checked <= today:
            raise ValueError('Future, reversed or unverified event/disclosure dates')
        if 'effective_date' in event:
            iso(event['effective_date'])  # Future effective dates are explicit, not plotted as completed events.
        global_event = event['category'] in ('Fed', 'U.S. CPI')
        if global_event:
            if 'plot_date' not in event:
                raise ValueError('U.S. events require explicit Tokyo-session plot_date')
            plotted = iso(event['plot_date'])
            if plotted <= when or (plotted - when).days > 4 or plotted.weekday() > 4:
                raise ValueError('Invalid Tokyo-session plot_date')
        elif 'plot_date' in event:
            raise ValueError('Only U.S. events may have a separate plot_date')
        if event['id'] in ids or identity(event) in identities:
            raise ValueError('Duplicate event ID or economic event identity')
        marker_id = event.get('legacy_id', event['id'])
        if marker_id in marker_ids:
            raise ValueError('Duplicate effective marker ID')
        marker_ids.add(marker_id)
        ids.add(event['id']); identities.add(identity(event))
        if 'legacy_id' in event:
            if event['legacy_id'] in legacy or not re.fullmatch(r'[A-Za-z0-9-]{1,80}', event['legacy_id']):
                raise ValueError('Duplicate/invalid legacy replacement')
            legacy.add(event['legacy_id'])
        sources = event['sources']
        if not isinstance(sources, list) or not 1 <= len(sources) <= 5:
            raise ValueError('One to five official sources required')
        urls, publication_dates = set(), []
        for source in sources:
            if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
                raise ValueError('Unexpected or missing source fields')
            official_url(source['url'], event['issuer']); text(source['title'], 'source title', 400)
            if source['url'] in urls:
                raise ValueError('Duplicate source')
            urls.add(source['url'])
            publication_dates.append(iso(source['published_date']))
            if publication_dates[-1] > checked:
                raise ValueError('Source postdates verification')
            if not isinstance(source['quotes'], list) or not 1 <= len(source['quotes']) <= 8:
                raise ValueError('Exact public evidence excerpts required')
            for quote in source['quotes']:
                text(quote, 'public evidence', 1800)
        if disclosed not in publication_dates:
            raise ValueError('Disclosure date must match a cited official publication')
    return registry


def upsert(registry, candidates, today=None):
    """Deterministic no-delete upsert. Reused ID cannot silently change identity."""
    validate(registry, today)
    validate({'schema_version': 1, 'events': candidates}, today)
    by_id = {event['id']: copy.deepcopy(event) for event in registry['events']}
    for event in candidates:
        if event['id'] in by_id and identity(by_id[event['id']]) != identity(event):
            raise ValueError('Existing event identity cannot change silently')
        if event['id'] in by_id and event['verified_on'] < by_id[event['id']]['verified_on']:
            raise ValueError('Stale verification cannot overwrite a newer reviewed record')
        if event['id'] in by_id and by_id[event['id']].get('legacy_id') != event.get('legacy_id'):
            raise ValueError('Existing legacy mapping cannot change silently')
        by_id[event['id']] = copy.deepcopy(event)
    result = {'schema_version': 1, 'events': sorted(by_id.values(), key=lambda e: (e['event_date'], e['id']))}
    return validate(result, today)


def validate_transition(base, proposed):
    """Check a direct JSON edit too: upsert must not be bypassed by deleting history."""
    validate(base); validate(proposed)
    base_ids = {event['id'] for event in base['events']}
    proposed_ids = {event['id'] for event in proposed['events']}
    if not base_ids <= proposed_ids:
        raise ValueError('Deleting reviewed event history is forbidden')
    upsert(base, proposed['events'])  # Enforces immutable identity/mapping and non-stale edits.
    return proposed


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC', html.unescape(value)).split())


def fetch_source(url, issuer):
    """Bounded official-only fetch; every redirect is checked before following."""
    official_url(url, issuer)
    class OfficialRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            official_url(newurl, issuer)
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    try:
        response = build_opener(OfficialRedirect()).open(Request(url, headers={'User-Agent': 'DailyMonitorEvidenceCheck/1.0'}), timeout=30)
    except Exception as exc:
        raise ValueError(f'Official source fetch failed for {url}: {type(exc).__name__}: {exc}') from exc
    with response:
        official_url(response.url, issuer)
        raw = response.read(15_000_001)
        if len(raw) > 15_000_000:
            raise ValueError('Official document exceeds evidence size limit')
        content_type = response.headers.get_content_type()
    if raw.startswith(b'%PDF-'):
        with tempfile.TemporaryDirectory() as folder:
            pdf, out = Path(folder)/'source.pdf', Path(folder)/'source.txt'
            pdf.write_bytes(raw)
            subprocess.run(['pdftotext', '-layout', str(pdf), str(out)], check=True, timeout=30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return out.read_text()
    if content_type not in ('text/html', 'text/plain', 'application/xhtml+xml'):
        raise ValueError('Unsupported official source content type')
    try:
        content = raw.decode('utf-8-sig', errors='strict')
    except UnicodeDecodeError:
        # Legacy Diet transcripts declare Shift_JIS; keep all other sources strict.
        if issuer != 'Diet' or not re.search(br'charset=[\"\']?shift[_-]jis', raw[:4096], re.I):
            raise
        content = raw.decode('cp932', errors='strict')
    if content_type == 'text/plain':
        return content
    parser = VisibleText(); parser.feed(content)
    return ' '.join(parser.parts)


def verify_sources(registry, fetch=fetch_source, today=None):
    validate(registry, today)
    cache = {}
    for event in registry['events']:
        for source in event['sources']:
            key = (source['url'], event['issuer'])
            if key not in cache:
                cache[key] = normalized(fetch(*key))
            for quote in source['quotes']:
                if normalized(quote) not in cache[key]:
                    raise ValueError(f'Official evidence no longer matches for {event["id"]}')
    return len(cache)


def chart_event(event, value):
    global_color = {'Fed': '#2563eb', 'U.S. CPI': '#0891b2'}
    marker = {'id': event.get('legacy_id', event['id']), 'policy_event_id': event['id'],
              'date': event.get('plot_date', event['event_date']), 'value': value,
              'event': event['title'], 'summary': event['summary'],
              'classification': event['classification'], 'category': event['category'],
              'color': global_color.get(event['category'], COLORS[event['direction']]),
              'verification': 'Official source verified; disclosed ' + event['disclosure_date'],
              'caveat': event['caveat'], 'date_basis': event['date_basis'],
              'disclosure_date': event['disclosure_date']}
    if 'plot_date' in event:
        marker['source_event_date'] = event['event_date']
    return marker


def sync_traces(p):
    global_categories = ('Fed', 'U.S. CPI')
    groups = [p['fiscal'], [e for e in p['context'] if e['category'] == 'BoJ'],
              [e for e in p['context'] if e['category'] == 'FX intervention'],
              [e for e in p['context'] if e['category'] in global_categories]]
    traces = p['figure']['data']
    if len(traces) == 4 and groups[3]:
        # A separately labeled global-news trace; never masquerade as BoJ events.
        global_trace = copy.deepcopy(traces[2])
        global_trace['name'] = 'U.S. Fed / CPI releases'
        global_trace['legendgroup'] = 'us-global-events'
        global_trace['showlegend'] = True
        traces.append(global_trace)
    if len(traces) not in (4, 5):
        raise ValueError('Unexpected report trace layout')
    for i, events in enumerate(groups[:len(traces)-1], 1):
        trace = traces[i]
        trace['x'] = [e['date'] for e in events]; trace['y'] = [e['value'] for e in events]
        trace['marker']['color'] = [e['color'] for e in events]
        if i == 1:
            trace['customdata'] = [[e['id'], e['event'], e['classification']] for e in events]
        else:
            trace['customdata'] = [[e['event'], e['classification'], e.get('verification', ''), e.get('caveat', '')] for e in events]
            trace['marker']['symbol'] = [
                ('diamond-open' if i == 2 else
                 ('star-open' if e['category'] == 'Fed' else 'circle-open') if i == 4 else
                 ('triangle-up-open' if 'unconfirmed' in e.get('verification', '').lower() else 'square-open'))
                for e in events]


def description(event, pending):
    e = lambda value: html.escape(value, quote=True)
    links = '; '.join(f'<a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["title"])}</a>' for s in event['sources'])
    waiting = ('<p class="event-meta">No matching market observation yet for: ' + e(', '.join(pending)) + '. No price is inferred.</p>') if pending else ''
    effective = (' Effective ' + e(event['effective_date']) + '.') if event.get('effective_date') else ''
    plotted = (' First Tokyo-session chart marker ' + e(event['plot_date']) +
               '; no same-day price reaction inferred.') if event.get('plot_date') else ''
    return (f'<article class="event-description" data-policy-id="{e(event["id"])}"><h4>{e(event["event_date"])} · {e(event.get("legacy_id", event["id"]))} · {e(event["title"])}</h4>'
            f'<p>{e(event["summary"])}</p><p class="event-meta">{e(event["classification"])} · {e(event["stage"])}. '
            f'Disclosed {e(event["disclosure_date"])}; verified {e(event["verified_on"])}. Date basis: {e(event["date_basis"])}.{effective}{plotted}</p>'
            f'<p class="event-meta">{e(event["caveat"])}</p><p class="event-meta">{links}</p>{waiting}</article>')


def apply_registry(document, registry):
    validate(registry)
    if not registry['events']:
        return document
    if document.count('<section class="report-section methodology">') != 1:
        raise ValueError('Expected one methodology anchor for source descriptions')
    match = PAYLOAD.search(document)
    if not match:
        raise ValueError('Report payload missing')
    payload = json.loads(match[2]); before = copy.deepcopy(payload)
    pending = {e['id']: [] for e in registry['events']}
    for key, p in payload.items():
        values = dict(zip(p['dates'], p['values']))
        for event in registry['events']:
            market_date = event.get('plot_date', event['event_date'])
            family = 'fiscal' if event['category'] == 'Fiscal' else 'context'
            marker_id = event.get('legacy_id', event['id'])
            existing = [e for e in p[family] if e.get('id') == marker_id or e.get('policy_event_id') == event['id']]
            if len(existing) > 1:
                raise ValueError('Ambiguous report replacement')
            if 'legacy_id' in event and not existing:
                raise ValueError('Legacy event replacement target is missing')
            if existing and (existing[0]['date'] != market_date or
                             existing[0].get('category', 'Fiscal') != event['category']):
                raise ValueError('Legacy event identity mismatch')
            if not existing and any(e['date'] == market_date and e['event'] == event['title'] for e in p[family]):
                raise ValueError('Possible unkeyed duplicate requires editorial resolution')
            if existing and market_date not in values:
                raise ValueError('Existing event lost its market observation; history retained')
            p[family] = [e for e in p[family] if e not in existing]
            if market_date in values:
                p[family].append(chart_event(event, values[market_date]))
            else:
                pending[event['id']].append(key)
        p['fiscal'].sort(key=lambda e: (e['date'], e['id']))
        p['context'].sort(key=lambda e: (e['date'], e.get('id', '')))
        sync_traces(p)
        if p['dates'] != before[key]['dates'] or p['values'] != before[key]['values'] or p['figure']['data'][0] != before[key]['figure']['data'][0]:
            raise AssertionError('Event rendering changed market data')
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False).replace('</', '<\\/')
    document = document[:match.start(2)] + encoded + document[match.end(2):]
    document = re.sub(re.escape(MANAGED_START) + '.*?' + re.escape(MANAGED_END), '', document, flags=re.S)
    for event in registry['events']:
        if event.get('legacy_id'):
            # Remove only the superseded baseline prose; all other history remains.
            pattern = r'<article class="event-description"><h4>' + re.escape(event['event_date']) + r' · ' + re.escape(event['legacy_id']) + r' · .*?</article>'
            document = re.sub(pattern, '', document, flags=re.S)
    additions = MANAGED_START + '<section class="report-section"><h2>Verified policy updates</h2><p>Official event dates and later disclosure dates are separate. These reviewed records supersede baseline notes for matching event IDs. This is not an exhaustive news calendar.</p>'
    additions += ''.join(description(e, pending[e['id']]) for e in registry['events'])
    additions += '</section>' + MANAGED_END
    document = document.replace('<section class="report-section methodology">', additions + '<section class="report-section methodology">', 1)
    # A retrospective allocation replaces uncertainty in markers and explanatory prose.
    if any(e.get('legacy_id') == 'FX26-4R' for e in registry['events']):
        document = document.replace('July 31 joint intervention is officially confirmed in US Eastern Time, disclosed August 3; July 30 remains separately marked as reported.',
                                    'The verified updates above give the later official daily amounts for the summer operations; the July 31 coordination statement uses US Eastern Time.')
    for key, p in payload.items():
        options = '<option value="">Focus on a policy event…</option>' + ''.join(
            f'<option value="{html.escape(e["id"], quote=True)}">{html.escape(e["id"] + " · " + e["date"] + " · " + e["event"])}</option>'
            for e in p['fiscal'] + p['context'] if e.get('id'))
        document = re.sub(r'(<select[^>]*data-event="' + key + r'"[^>]*>).*?(</select>)', lambda m: m[1] + options + m[2], document, flags=re.S)
    document = document.replace("n.textContent='26 fiscal / debt-management events,", "n.textContent=p.fiscal.length+' fiscal / debt-management events,")
    latest = max(e['verified_on'] for e in registry['events'])
    document = re.sub(r'(?:Event annotations retained through October 26, 2026\.|Baseline annotations retained through October 26, 2026; verified updates checked through \d{4}-\d{2}-\d{2}\.)',
                      f'Baseline annotations retained through October 26, 2026; verified updates checked through {latest}.', document)
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, default=REGISTRY)
    parser.add_argument('--base-registry', type=Path, help='Previous reviewed registry for no-delete/identity checks')
    parser.add_argument('--verify-sources', action='store_true')
    parser.add_argument('--candidates', type=Path, help='Public-only candidate registry to upsert into a distinct output')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if (args.candidates or args.report) and not args.verify_sources:
        parser.error('Draft preparation requires --verify-sources; deployment uses reviewed registry directly')
    registry = validate(json.loads(args.registry.read_text()))
    if args.candidates:
        if args.report or not args.output or args.output.resolve() == args.registry.resolve():
            parser.error('Upsert requires a distinct --output and no --report')
        candidates = validate(json.loads(args.candidates.read_text()))
        registry = upsert(registry, candidates['events'])
    if args.base_registry:
        validate_transition(json.loads(args.base_registry.read_text()), registry)
    if args.verify_sources:
        print(f'Official source/evidence checks passed: {verify_sources(registry)} distinct pages')
    if args.candidates:
        args.output.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n')
    if args.report:
        if not args.output or args.output.resolve() == args.report.resolve():
            parser.error('Render to a distinct --output; never overwrite the committed baseline')
        args.output.write_text(apply_registry(args.report.read_text(), registry))
    print(f'Validated {len(registry["events"])} public event records; no publication performed')


if __name__ == '__main__':
    main()
