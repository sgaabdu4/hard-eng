import 'package:app/l10n/app_localizations.dart';
import 'package:app/main.dart' as app;
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('starter screen shows 0, then 1 after one tap on the add button', (
    WidgetTester tester,
  ) async {
    final l10n = lookupAppLocalizations(const Locale('en'));
    app.main();
    await tester.pump();
    expect(find.text(l10n.counterValue(0)), findsOneWidget);

    await tester.tap(find.byTooltip(l10n.counterIncrementTooltip));
    await tester.pump();

    expect(find.text(l10n.counterValue(1)), findsOneWidget);
    expect(find.text(l10n.counterValue(0)), findsNothing);
  });
}
