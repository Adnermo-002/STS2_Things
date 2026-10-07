"""Rig definition for The Legacy (心脏残躯).  All positions in source-image pixels."""
ORIGIN=(679.0,660.0)          # skeleton origin (image px) -> spine (0,0)
def S(p): return (round(p[0]-ORIGIN[0],2), round(ORIGIN[1]-p[1],2))

# name, parent, image position
BONES=[
 ('root',None,(679,660)),
 ('body','root',(679,640)),
 ('heart','body',(650,480)),
 ('bulb_base','heart',(640,520)),
 ('bulb','bulb_base',(770,390)),
 ('atrium','heart',(560,320)),
 ('tube_a','atrium',(335,262)),
 ('tube_b','atrium',(305,372)),
 ('mid_lobe','heart',(520,480)),
 ('mid_tip','mid_lobe',(260,468)),
 ('bottom_lobe','heart',(650,620)),
 ('bottom_tip','bottom_lobe',(360,602)),
 ('right_lobe','heart',(940,600)),
 ('back','body',(950,320)),
 ('purple_mass','back',(900,300)),
 ('purple_top','purple_mass',(800,215)),
 ('ptube_l','purple_top',(742,132)),
 ('ptube_r','purple_top',(768,112)),
 ('purple_lr','back',(1100,480)),
 ('plr_a','purple_lr',(1185,450)),
 ('plr_b','purple_lr',(1185,525)),
 ('blue','body',(950,420)),
 ('blue_main','blue',(900,385)),
 ('blue_up','blue_main',(1195,365)),
 ('blue_down','blue',(1150,432)),
 ('blue_bottom','blue',(1000,470)),
]
# per body part: list of (bone, segment start, segment end) used for skin weights
BODY_SKIN={
 'purple_top':[('purple_top',(805,215),(775,150)),('ptube_l',(742,132),(660,82)),('ptube_r',(768,112),(725,42))],
 'purple_mass':[('purple_mass',(820,250),(1000,250))],
 'purple_lr':[('purple_lr',(1080,470),(1170,480)),('plr_a',(1185,450),(1335,425)),('plr_b',(1185,525),(1240,592))],
 'blue_bottom':[('blue_bottom',(990,470),(1050,545))],
 'blue_main':[('blue_main',(900,385),(1140,410)),('blue_up',(1195,365),(1215,280))],
 'blue_down':[('blue_down',(1150,432),(1275,500))],
 'right_lobe':[('right_lobe',(930,420),(940,600))],
 'mid_lobe':[('mid_lobe',(620,470),(380,480)),('mid_tip',(260,468),(95,470))],
 'bottom_lobe':[('bottom_lobe',(900,600),(480,620)),('bottom_tip',(360,602),(160,585))],
 'atrium':[('atrium',(640,280),(420,300)),('tube_a',(335,262),(165,255)),('tube_b',(305,372),(120,375))],
 'bulb':[('bulb_base',(560,570),(680,480)),('bulb',(740,420),(800,330))],
}
GLOW_OF={'atrium_glow':'atrium','bulb_glow':'bulb'}
# chain parts (weeds / corals): parent bone, base, tip, n bones
CHAIN_OVERRIDE={
 'weed_ground_left':((160,565),(8,545)),
 'weed_ground_right':((1248,540),(1352,535)),
 'weed_edge_right':((1308,492),(1356,478)),
 'weed_ground_bl':((300,662),(436,614)),
 'weed_bottom_mid':((522,676),(535,418)),
 'weed_bottom_right':((1090,622),(1187,420)),
 'weed_blue':((1062,382),(1008,292)),
}
CHAIN_PARENT={
 'coral_pink':'mid_lobe','coral_purple':'body',
 'weed_top_left':'atrium','weed_left':'body','weed_bottom_mid':'bottom_lobe','weed_bottom_right':'body',
 'weed_right':'purple_mass','weed_ground_left':'body','weed_back_a':'purple_mass','weed_back_b':'purple_top',
 'weed_back_c':'purple_mass','weed_back_d':'purple_mass','weed_blue':'blue_main','weed_ground_right':'body',
 'weed_edge_right':'body','weed_ground_bl':'body',
}
