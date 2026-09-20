"""Royalty setup, overview, calculator and statement upload screens."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.views import _bump
from royalties import services
from royalties.models import CURRENCIES, SOURCES, Calculation, IncomeSource, RoyaltyTransaction, Statement


@login_required
def setup(request):
    """Port of the RoyaltySetup component. Selecting a source connects nothing."""
    if request.method == 'POST':
        name = request.POST.get('source', '')
        if name in SOURCES:
            existing = IncomeSource.objects.filter(user=request.user, name=name).first()
            if existing:
                existing.delete()
            else:
                IncomeSource.objects.create(user=request.user, name=name)
            _bump(request.user)
        return redirect('/royalty-setup')
    selected = list(IncomeSource.objects.filter(user=request.user).values_list('name', flat=True))
    return render(
        request,
        'royalty_setup.html',
        {'sources': SOURCES, 'selected': selected, 'current_page': 'royalty setup'},
    )


@login_required
def overview(request):
    """Port of the Royalties component."""
    statements = list(request.user.statements.all())
    return render(
        request,
        'royalties.html',
        {
            'earnings': sorted(services.totals(statements).items()),
            'calculations': Calculation.objects.filter(owner=request.user),
            'current_page': 'Royalties',
        },
    )


@login_required
def calculator(request):
    """Port of the Calculator component.

    The estimate is a scenario built from the creator's own rate, and the saved
    record keeps the rate provenance and formula with it (PRD 10.2).
    """
    result = None
    error = ''
    if request.method == 'POST':
        if request.POST.get('action') == 'save':
            return _save_calculation(request)
        try:
            amount = services.estimate(
                request.POST.get('streams'), request.POST.get('rate'), request.POST.get('share')
            )
            result = {
                'platform': request.POST.get('platform', ''),
                'streams': int(request.POST.get('streams')),
                'rate': Decimal(request.POST.get('rate')),
                'share': Decimal(request.POST.get('share')),
                'currency': request.POST.get('currency', 'USD'),
                'amount': amount,
            }
        except (services.StatementError, TypeError, ValueError) as problem:
            error = str(problem) or 'Enter valid streams, rate and ownership.'
    return render(
        request,
        'calculator.html',
        {
            'result': result,
            'error': error,
            'currencies': [code for code, _ in CURRENCIES],
            'current_page': 'royalty calculator',
        },
    )


def _save_calculation(request):
    try:
        amount = services.estimate(
            request.POST.get('streams'), request.POST.get('rate'), request.POST.get('share')
        )
    except services.StatementError as problem:
        messages.info(request, str(problem))
        return redirect('/royalty-calculator')
    Calculation.objects.create(
        owner=request.user,
        platform=(request.POST.get('platform') or '')[:300],
        streams=int(request.POST.get('streams')),
        rate=Decimal(request.POST.get('rate')),
        share=Decimal(request.POST.get('share')),
        currency=request.POST.get('currency', 'USD'),
        amount=amount,
        assumptions={
            'entered_by': 'creator',
            'covers': 'master recording streaming income only',
            'excludes': 'composition royalties unless separately modelled',
        },
    )
    _bump(request.user)
    messages.info(request, 'Estimate saved.')
    return redirect('/royalties')


@login_required
def upload(request):
    """Port of the Upload component, with the CSV parsed on the server."""
    error = ''
    if request.method == 'POST':
        if request.POST.get('action') == 'remove':
            statement = get_object_or_404(Statement, pk=request.POST.get('id'), owner=request.user)
            statement.delete()
            _bump(request.user)
            messages.info(request, 'Statement removed. You can import it again.')
            return redirect('/royalty-upload')
        error = _import(request)
        if not error:
            return redirect('/royalty-upload')
    statements = list(request.user.statements.prefetch_related('transactions'))
    rows = []
    for statement in statements:
        transactions = list(statement.transactions.all())
        rows.append(
            {
                'id': statement.id,
                'name': statement.name,
                'rows': transactions[:100],
                'total': len(transactions),
            }
        )
    return render(
        request,
        'upload.html',
        {
            'statements': rows,
            'earnings': sorted(services.totals(statements).items()),
            'error': error,
            'current_page': 'royalty upload',
        },
    )


def _import(request):
    upload_file = request.FILES.get('statement')
    if not upload_file:
        return ''
    if not upload_file.name.lower().endswith('.csv') or upload_file.size > services.MAX_CSV_BYTES:
        return 'Choose a CSV file smaller than 5 MB.'
    raw = upload_file.read()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return 'Unable to read this CSV. Check column counts and quotation marks.'
    try:
        rows = services.normalize_statement(services.parse_csv(text))
    except services.StatementError as problem:
        return str(problem)
    digest = services.fingerprint(rows)
    if Statement.objects.filter(owner=request.user, name=upload_file.name, row_fingerprint=digest).exists():
        return 'This statement is already imported.'
    statement = Statement.objects.create(
        owner=request.user,
        name=upload_file.name[:300],
        original_csv=raw,
        row_fingerprint=digest,
    )
    RoyaltyTransaction.objects.bulk_create(
        [
            RoyaltyTransaction(
                statement=statement,
                position=index,
                track=row['track'][:500],
                platform=row['platform'][:300],
                amount=row['amount'],
                currency=row['currency'],
                work=row['work'][:500],
                recording_id=row['recording_id'][:120],
                territory=row['territory'][:120],
                usage_type=row['usage_type'][:120],
                payee=row['payee'][:300],
            )
            for index, row in enumerate(rows)
        ]
    )
    _bump(request.user)
    messages.info(request, f'Imported {len(rows)} rows.')
    return ''


def sample_csv(request):
    """The sample statement the Upload screen offers for download."""
    response = HttpResponse(services.SAMPLE_CSV, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="statement-template.csv"'
    return response
