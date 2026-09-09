Name = "Goal"

[General]
TurnFrequency						= 2		// (2)		This is how often the goal server gets run. 4 = 4 turns

[Monitor]
ViewGoalActivity					= 2		// (2)		2=view all goal activity, 1=view main activity, 0=view activity not logged
ReportInterval						= 10	// (100)	Will report every n simulated characters (monitoring simulation)

[Simulation]
SystemRepairPercentage				= 25	// Percentage of total system damage required before AIs will stop their goal and return to base to be repaired.
HullRepairPercentage				= 25	// Percentage of total hull damage required before AIs will stop their goal and return to base to be repaired.

[GeneralActionOdds]
											// NOTE: All odds are during the turn
OddsAttack							= 50	// 0...100 chance that AI will attack an enemy in hex
OddsAttackPlanet					= 01	// 0...100 chance that AI will attack an enemy planet in hex
OddsAttackStarbase					= 02	// 0...100 chance that AI will attack an enemy starbase in hex
OddsAttackHuman						= 80	// 0...100 chance that AI will attack a human enemy in hex
OddsAttackButGoalDisagrees			= 10	// 0...100 chance that AI will attack an enemy in hex, considering that the goal disagrees with attack
OddsAttackHumanButGoalDisagrees		= 30	// 0...100 chance that AI will attack a human enemy in hex, considering that the goal disagrees with attack
OddsForfeitIfAttacked				= 30	// 0...100 chance that AI will forfeit when attacked
OddsForfeitIfAttackedByHuman		= 40	// 0...100 chance that AI will forfeit when attacked by a human
OddsAcceptDefenders					= 90	// 0...100 chance that AI will allow someone else to help defend
OddsAcceptHumanDefenders			= 100	// 0...100 chance that AI will allow a human to help defend
OddsJoinFleet						=  5	// 0...100 chance that AI will wish to join a fleet
OddsJoinHumanFleet					= 50	// 0...100 chance that AI will wish to join a human fleet
OddsLeaveFleet						=  1	// 0...100 chance that AI will leave a fleet during the turn
OddsLeaveHumanFleet					=  0	// 0...100 chance that AI will leave a human fleet during the turn
OddsApproveNewFleetMember			= 80	// 0...100 chance that AI will approve someone joining their fleet
OddsApproveNewHumanFleetMember		= 90	// 0...100 chance that AI will approve a human joining their fleet

//	Scenarios
//		"NoScenario"						Nothing given to character
//		"InternalPatrol"					Will patrol within allied territory
//		"BorderPatrolDefense"				Will patrol on allied side of border
//		"BorderPatrolOffense"				Will patrol on enemy side of border
//		"Offense"							Will march into enemy territory and wander
//		"OffensePlanet"						Will pick enemy planet to march to and attack
//		"OffenseStarbase"					Will pick enemy starbase to march to and attack
//		"DefendPlanet"						Will head to allied planet and remain for a period of time defending
//		"DefendStarbase"					Will head to allied starbase and remain for a period of time defending
//		"DefendBorder"						Will head to allied side of border and remain for a period of time defending
//		"ExpandTerritory"					Will head to neutral territory and remain for a period of time
//		"DeliverStarbase"					Will take Starbase to available allied hex and deliver (only possible if empire has strength and hex remains allied)
//		"DeliverBattleStation"				Will take BattleStation to available allied hex and deliver (only possible if empire has strength and hex remains allied)
//		"DeliverBaseStation"				Will take BaseStation to available allied hex and deliver (only possible if empire has strength and hex remains allied)
//		"DeliverWeaponsPlatform"			Will take Weapons Platform to available allied hex and deliver (only possible if empire has strength and hex remains allied)
//		"DeliverListeningPost"				Will take Listening Post to available allied hex and deliver (only possible if empire has strength and hex remains allied)
//		"HuntEnemy"							Will choose a random enemy and begin hunting


// NOTE:
// The ScenarioOdds array for a given empire is totalled and each item's # is the odds ratio against that total.  Therefore
// one scenario will be chosen and it's chance is based on the ratio of it's Odds vs the total of all odds for the empire.
// (this, of course, includes "NoScenario")

[ScenarioOdds/Federation]
"NoScenario"			 =  600
"InternalPatrol"		 =  300
"BorderPatrolDefense"	 =  200
"BorderPatrolOffense"	 =  100
"Offense"				 =  070
"OffensePlanet"			 =  010
"OffenseStarbase"		 =  030
"DefendPlanet"			 =  200
"DefendStarbase"		 =  150
"DefendBorder"			 =  200
"ExpandTerritory"		 =  100
"DeliverStarbase"		 =  002
"DeliverBattleStation"	 =  001
"DeliverBaseStation"	 =  002
"DeliverWeaponsPlatform" =  003
"DeliverListeningPost"	 =  005
"HuntEnemy"				 =  020

[ScenarioOdds/Klingon]
"NoScenario"			 =  400
"InternalPatrol"		 =  200
"BorderPatrolDefense"	 =  250
"BorderPatrolOffense"	 =  350
"Offense"				 =  150
"OffensePlanet"			 =  040
"OffenseStarbase"		 =  060
"DefendPlanet"			 =  100
"DefendStarbase"		 =  150
"DefendBorder"			 =  250
"ExpandTerritory"		 =  350
"DeliverStarbase"		 =  002
"DeliverBattleStation"	 =  001
"DeliverBaseStation"	 =  002
"DeliverWeaponsPlatform" =  003
"DeliverListeningPost"	 =  005
"HuntEnemy"				 =  250

[ScenarioOdds/Romulan]
"NoScenario"			 =  500
"InternalPatrol"		 =  400
"BorderPatrolDefense"	 =  300
"BorderPatrolOffense"	 =  350
"Offense"				 =  100
"OffensePlanet"			 =  040
"OffenseStarbase"		 =  060
"DefendPlanet"			 =  100
"DefendStarbase"		 =  150
"DefendBorder"			 =  250
"ExpandTerritory"		 =  350
"DeliverStarbase"		 =  002
"DeliverBattleStation"	 =  001
"DeliverBaseStation"	 =  002
"DeliverWeaponsPlatform" =  003
"DeliverListeningPost"	 =  005
"HuntEnemy"				 =  250

[ScenarioOdds/Borg]
"NoScenario"			 =  400
"InternalPatrol"		 =  300
"BorderPatrolDefense"	 =  300
"BorderPatrolOffense"	 =  100
"Offense"				 =  050
"OffensePlanet"			 =  010
"OffenseStarbase"		 =  020
"DefendPlanet"			 =  500
"DefendStarbase"		 =  400
"DefendBorder"			 =  200
"ExpandTerritory"		 =  200
"DeliverStarbase"		 =  002
"DeliverBattleStation"	 =  001
"DeliverBaseStation"	 =  002
"DeliverWeaponsPlatform" =  003
"DeliverListeningPost"	 =  005
"HuntEnemy"				 =  050

[ScenarioOdds/Species8472]
"NoScenario"			 =  600
"InternalPatrol"		 =  400
"BorderPatrolDefense"	 =  300
"BorderPatrolOffense"	 =  100
"Offense"				 =  100
"OffensePlanet"			 =  050
"OffenseStarbase"		 =  070
"DefendPlanet"			 =  300
"DefendStarbase"		 =  200
"DefendBorder"			 =  150
"ExpandTerritory"		 =  050
"DeliverStarbase"		 =  000
"DeliverBattleStation"	 =  000
"DeliverBaseStation"	 =  000
"DeliverWeaponsPlatform" =  000
"DeliverListeningPost"	 =  000
"HuntEnemy"				 =  100

[ScenarioOdds/Cardassian]
"NoScenario"			 =  500
"InternalPatrol"		 =  400
"BorderPatrolDefense"	 =  300
"BorderPatrolOffense"	 =  350
"Offense"				 =  100
"OffensePlanet"			 =  040
"OffenseStarbase"		 =  060
"DefendPlanet"			 =  100
"DefendStarbase"		 =  150
"DefendBorder"			 =  250
"ExpandTerritory"		 =  350
"DeliverStarbase"		 =  002
"DeliverBattleStation"	 =  001
"DeliverBaseStation"	 =  002
"DeliverWeaponsPlatform" =  003
"DeliverListeningPost"	 =  005
"HuntEnemy"				 =  250

[ScenarioOdds/Ferengi]
"NoScenario"			 =  400
"InternalPatrol"		 =  300
"BorderPatrolDefense"	 =  200
"BorderPatrolOffense"	 =  050
"Offense"				 =  050
"OffensePlanet"			 =  010
"OffenseStarbase"		 =  030
"DefendPlanet"			 =  200
"DefendStarbase"		 =  150
"DefendBorder"			 =  400
"ExpandTerritory"		 =  150
"DeliverStarbase"		 =  000
"DeliverBattleStation"	 =  000
"DeliverBaseStation"	 =  000
"DeliverWeaponsPlatform" =  000
"DeliverListeningPost"	 =  000
"HuntEnemy"				 =  020

[ScenarioOdds/Rakellian]
"NoScenario"			 =  400
"InternalPatrol"		 =  300
"BorderPatrolDefense"	 =  200
"BorderPatrolOffense"	 =  050
"Offense"				 =  050
"OffensePlanet"			 =  010
"OffenseStarbase"		 =  030
"DefendPlanet"			 =  200
"DefendStarbase"		 =  150
"DefendBorder"			 =  400
"ExpandTerritory"		 =  150
"DeliverStarbase"		 =  000
"DeliverBattleStation"	 =  000
"DeliverBaseStation"	 =  000
"DeliverWeaponsPlatform" =  000
"DeliverListeningPost"	 =  000
"HuntEnemy"				 =  020

[ScenarioOdds/Pirate]
"NoScenario"			 =  400
"InternalPatrol"		 =  300
"BorderPatrolDefense"	 =  200
"BorderPatrolOffense"	 =  050
"Offense"				 =  050
"OffensePlanet"			 =  010
"OffenseStarbase"		 =  030
"DefendPlanet"			 =  200
"DefendStarbase"		 =  150
"DefendBorder"			 =  400
"ExpandTerritory"		 =  150
"DeliverStarbase"		 =  000
"DeliverBattleStation"	 =  000
"DeliverBaseStation"	 =  000
"DeliverWeaponsPlatform" =  000
"DeliverListeningPost"	 =  000
"HuntEnemy"				 =  020


// NOTE: No neutral (do not exist as empire, cannot create goals)
