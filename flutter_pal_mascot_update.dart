// Updated PalMascot widget to use the actual Pal image
// Replace the contents of lib/presentation/widgets/pal_mascot.dart with this:

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';

class PalMascot extends StatelessWidget {
  final double size;
  final String emotion;
  final bool showPulse;

  const PalMascot({
    Key? key,
    this.size = 60,
    this.emotion = 'happy',
    this.showPulse = true,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        // Pulse effect
        if (showPulse)
          Container(
            width: size * 1.3,
            height: size * 1.3,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [
                  Colors.purple.withOpacity(0.3),
                  Colors.pink.withOpacity(0.1),
                  Colors.transparent,
                ],
              ),
            ),
          )
              .animate(onPlay: (controller) => controller.repeat())
              .scale(
                begin: const Offset(0.95, 0.95),
                end: const Offset(1.05, 1.05),
                duration: const Duration(seconds: 2),
                curve: Curves.easeInOut,
              )
              .fade(
                begin: 0.5,
                end: 1.0,
                duration: const Duration(seconds: 2),
                curve: Curves.easeInOut,
              ),
        
        // Pal mascot image
        Image.asset(
          'assets/images/pal_mascot.png',
          width: size,
          height: size,
          fit: BoxFit.contain,
        )
            .animate()
            .scale(
              begin: const Offset(0, 0),
              end: const Offset(1, 1),
              duration: const Duration(milliseconds: 500),
              curve: Curves.elasticOut,
            ),
        
        // Sparkle effects around Pal
        if (emotion == 'excited' || emotion == 'happy')
          ...List.generate(3, (index) {
            final angle = (index * 120) * 3.14159 / 180;
            final distance = size * 0.6;
            return Positioned(
              left: size / 2 + distance * (angle.cos() as double) - 10,
              top: size / 2 + distance * (angle.sin() as double) - 10,
              child: Icon(
                Icons.star,
                size: 16,
                color: Colors.cyan,
              )
                  .animate(onPlay: (controller) => controller.repeat())
                  .scale(
                    begin: const Offset(0.8, 0.8),
                    end: const Offset(1.2, 1.2),
                    duration: Duration(milliseconds: 800 + index * 200),
                  )
                  .fade(
                    begin: 0.3,
                    end: 1.0,
                    duration: Duration(milliseconds: 800 + index * 200),
                  ),
            );
          }),
      ],
    );
  }
}

// For the main navigation, update the center tab:
class MainNavigation extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      bottomNavigationBar: BottomAppBar(
        shape: CircularNotchedRectangle(),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            // ... other navigation items
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          HapticFeedback.mediumImpact();
          Navigator.push(
            context,
            CupertinoPageRoute(
              builder: (_) => PalChatPage(),
            ),
          );
        },
        backgroundColor: Colors.transparent,
        elevation: 0,
        child: Hero(
          tag: 'pal_mascot',
          child: Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Colors.purple, Colors.pink],
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.purple.withOpacity(0.3),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Padding(
              padding: const EdgeInsets.all(8.0),
              child: Image.asset(
                'assets/images/pal_mascot.png',
                fit: BoxFit.contain,
              ),
            ),
          ),
        ),
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
    );
  }
}

// In the PalChatPage header, also use the actual image:
class PalChatHeader extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Colors.purple.shade400,
            Colors.pink.shade400,
          ],
        ),
        borderRadius: const BorderRadius.only(
          bottomLeft: Radius.circular(30),
          bottomRight: Radius.circular(30),
        ),
      ),
      child: SafeArea(
        child: Column(
          children: [
            Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back_ios, color: Colors.white),
                  onPressed: () => Navigator.pop(context),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.more_vert, color: Colors.white),
                  onPressed: () {
                    // Show options menu
                  },
                ),
              ],
            ),
            const SizedBox(height: 10),
            Hero(
              tag: 'pal_mascot',
              child: Image.asset(
                'assets/images/pal_mascot.png',
                width: 80,
                height: 80,
                fit: BoxFit.contain,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'Pal',
              style: TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Your Skincare Companion',
              style: TextStyle(
                color: Colors.white.withOpacity(0.9),
                fontSize: 14,
              ),
            ),
          ],
        ),
      ),
    );
  }
}