use SFC3;

create table TableNames
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	Name varchar( 255 ) not null,
);

create table TurnDescription
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	Turn int not null,
);

create table DatabaseDescription
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	NextID int not null,
	NextLockID int not null,
);


create table MapDescription 
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,
	
	Width int not null,
	Height int not null,
);
	 
create table MapHex 
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	X int not null,
	Y int not null,
	Race int not null,
	PlanetRace int not null,
	TerrainType int not null,
	PlanetType int not null,
	StarbaseType int not null,
	BaseEconomicPoints int not null,
	CurrentEconomicPoints int not null,
	BaseVictoryPoints int not null,
	CurrentVictoryPoints int not null,
	BaseSpeedPoints double precision,
	CurrentSpeedPoints double precision,

	constraint XYIndex unique( X, Y )
);
	
create table PoliticalTensionMatrix
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	MatrixSize int not null,
	Matrix image not null,
	AllyRatio double precision,
	NeutralRatio double precision,
);

create table ServCharacter
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	WONLogon varchar(255) not null,
	LastLoggedOn bigint not null,
	MissionsPlayedVector varchar(8000) not null,
	IPAddress varchar(15) not null,
	NextMissionTitle varchar(255) not null,
	NextMissionScore bigint not null,
	HomeWorldLocationX int not null,
	HomeWorldLocationY int not null,
	LastMustPlayLocationX int not null,
	LastMustPlayLocationY int not null,
	PreparedMissionsID int not null,
	OpenShipBids varchar(255) not null,
	CharacterName varchar(255) not null,
	ShipCacheVectorSize int not null,
	ShipCacheVector image not null,
	StarbaseID int not null,
	StarbaseClass int not null,
	CharacterRace int not null,
	CharacterRank int not null,
	Flags int not null,
	CharacterLastBattleResult float not null,
	CharacterLocationX int not null,
	CharacterLocationY int not null,
	CharacterRating int not null,
	Medals int not null,
	CharacterCurrentPrestige int not null,
	CharacterLifetimePrestige int not null,
	CharacterCurrentDisrepute int not null,
	CharacterLifetimeDisrepute int not null,
	CharacterBattlesPlayed int not null,
	MissionSlotIdx int not null,
	MoveCompletes int not null,
	MoveDestinationX int not null,
	MoveDestinationY int not null,
	HailSize int not null,
	Hail image not null,
	Personality int not null,
	GoalState int not null,
	GoalIDs varchar(255) not null,
	FleetLeaderID int not null,
	FleetIDs varchar(255) not null,
	DismissedIDs varchar(255) not null,
	FleetName varchar(255) not null,
	ServLanguage int not null,
);

create index CharacterNameIndex on ServCharacter (CharacterName)
create index WONLogonIndex on ServCharacter (WONLogon)
	
create table BidItem
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	BiddingHasBegun tinyint not null,
	ItemDescription varchar(255) not null,
	ItemID int not null,
	ItemInfo int not null,
	AuctionValue int not null,
	AuctionRate double precision,
	TurnOpened int not null,
	TurnToClose int not null,
	Closing int not null,
	CurrentBid int not null,
	BidOwnerID int not null,
	TurnBidMade int not null,
	BidMaximum int not null,
	Escrow int not null,
	ItemDetailsSize int not null,
	ItemDetails image not null,
);	

create index BidOwnerIDIndex on BidItem (BidOwnerID)
create index ItemIDIndex on BidItem (ItemID)

	
create table Ship
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	Owner int not null,
	IsInAuction tinyint not null,
	Race int not null,
	ClassType int not null,
	EPV int not null,
	ShipClassName varchar(255) not null,
	TurnCreated int not null,
	Name varchar(255) not null,

	TNGShipSize int not null,
	TNGShip image not null,

	DamageSize int not null,
	Damage image not null,

	StoresSize int not null,
	Stores image not null,

	Flags int not null,
	RawHullCost int not null,
);		
	
create table CampaignInfo
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	TemplateName varchar(255) not null,
	Description varchar(255) not null,
	EarlyMapName varchar(255) not null,
	MidMapName varchar(255) not null,
	LateMapName varchar(255) not null,
	MissionList varchar(8000) not null,
	RaceList varchar(255) not null,
	CampaignDifficulty int not null,
	TriggerPrestige int not null,
	TriggerMission varchar(255) not null,
	CampaignName varchar(255) not null,
	CharacterName varchar(255) not null,
	CharacterRace int not null,
	ServerPassword varchar(255) not null,
	CurrentTurn int not null,
	CurrentYear int not null,
	CurrentTurnsPerYear int not null,
	CurrentMilliSecondsPerTurn int not null,
	CurrentBaseYear int not null,
	PlayersCurrent int not null,
	PlayersMax int not null,
	PlayersLoggedOnCurrent int not null,
	PlayersLoggedOnMax int not null,
	ServerVersion varchar(255) not null,
	ValidClientVersion varchar(255) not null,
	GameOver int not null,
);		

create table Notify
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	Category int not null,
	NotifyEvent int not null,
	ExtraID int not null,
	NameToNotifySize int not null,
	NameToNotify image not null,
	DataID int not null,
);

create table NewsStory
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	PersistenceLevel int not null,
	UrgencyLevel int not null,
	Category int not null,
	MessageEnglish varchar(1024) not null,
	MessageGerman varchar(1024) not null,
	NewsTime bigint not null,
	TimeDetail bigint not null,
	Color bigint not null,
);		

create table PreparedMissions
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	CharacterID int not null,
	MissionProfilesSize int not null,
	MissionProfiles image not null,
	HaveTriggeredMission int not null,
	NearbyCharactersSize int not null,
	NearbyCharacters image not null,
	X int not null,
	Y int not null,
);		

create index CharacterIDIndex on PreparedMissions (CharacterID)


create table Goal
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	ActorTypeRawName varchar(255) not null,
	ActorSize int not null,
	Actor image not null,
	Action int not null,
	CharacterID int not null,
);

create index CharacterIDIndex on Goal (CharacterID)


create table Officer
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	OfficerItemSize int not null,
	OfficerItem image not null,
	AtBaseID int not null,
	InReviewID int not null,
	AtBaseClass int not null,
	AtBaseRace int not null,
	Race int not null,
);

create table Banned
(
	ID int primary key not null,
	Locked DateTime,
	LockID int,

	IPAddress varchar(255),
	GameSpyName varchar(255),
);

create index IPAddressIndex on Banned (IPAddress)
create index GameSpyNameIndex on Banned (GameSpyName)


/*
NOTE:  The following rules apply:
1) These table names much match the names used internal to Server (AsyncDBMulti.cpp)
2) The ID/order is not important, but must NOT change for the life of the database (until restarted)
3) During the life of the database, you can add to this table, but not modify or delete
4) This table will be REMOVED once I add the "show tables" logic to the server
*/

insert into TableNames ( ID, Name )	Values (  2, 'TableNames'				);
insert into TableNames ( ID, Name )	Values (  3, 'TurnDescription'			);
insert into TableNames ( ID, Name )	Values (  4, 'DatabaseDescription'		);
insert into TableNames ( ID, Name )	Values (  5, 'MapDescription'			);
insert into TableNames ( ID, Name )	Values (  6, 'MapHex'					);
insert into TableNames ( ID, Name )	Values (  7, 'PoliticalTensionMatrix'	);
insert into TableNames ( ID, Name )	Values (  8, 'ServCharacter'			);
insert into TableNames ( ID, Name )	Values (  9, 'BidItem'					);
insert into TableNames ( ID, Name )	Values ( 10, 'Ship'						);
insert into TableNames ( ID, Name )	Values ( 11, 'CampaignInfo'				);
insert into TableNames ( ID, Name )	Values ( 12, 'Notify'					);
insert into TableNames ( ID, Name )	Values ( 13, 'NewsStory'				);
insert into TableNames ( ID, Name )	Values ( 14, 'PreparedMissions'			);
insert into TableNames ( ID, Name )	Values ( 15, 'Goal'						);
insert into TableNames ( ID, Name )	Values ( 16, 'Officer'					);
insert into TableNames ( ID, Name )	Values ( 17, 'Banned'					);

insert into DatabaseDescription ( ID, Locked, LockID, NextID, NextLockID ) Values( 1, '1969-12-31 19:00:00', 0, 18, 1 );

select * from DatabaseDescription;
select * from TableNames;
