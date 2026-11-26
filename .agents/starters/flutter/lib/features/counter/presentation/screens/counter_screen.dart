import 'package:app/core/extensions/extensions.dart';
import 'package:app/core/widgets/app_action_button.dart';
import 'package:app/features/counter/presentation/notifiers/counter_notifier.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:material_ui/material_ui.dart';

class CounterScreen extends ConsumerWidget {
  const CounterScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = context.l10n;
    final count = ref.watch(counterProvider);
    return Scaffold(
      body: Center(child: Text(l10n.counterValue(count))),
      floatingActionButton: AppActionButton(
        onPressed: () => ref.read(counterProvider.notifier).increment(),
        tooltip: l10n.counterIncrementTooltip,
        icon: Icons.add,
      ),
    );
  }
}
