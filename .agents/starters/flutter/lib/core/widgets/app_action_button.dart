import 'package:material_ui/material_ui.dart';

class AppActionButton extends StatelessWidget {
  const AppActionButton({
    required this.onPressed,
    required this.tooltip,
    required this.icon,
    super.key,
  });

  final VoidCallback onPressed;
  final String tooltip;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton(
      onPressed: onPressed,
      heroTag: null,
      tooltip: tooltip,
      child: Icon(icon),
    );
  }
}
