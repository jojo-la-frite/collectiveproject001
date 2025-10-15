import os
import json
import random
import maya.mel as mel
import maya.cmds as cmds
import mayaUsd

MAYA_LOCATION = os.environ['MAYA_LOCATION']
mel.eval('source "'+MAYA_LOCATION+'/scripts/others/hikDefinitionOperations.mel"')

def getLayerByName(layer_name):
    stage = cmds.ls(type='mayaUsdProxyShape', long=True)
    stage = mayaUsd.ufe.getStage(stage[0])
    all_layers = stage.GetUsedLayers()
    for layer in all_layers :
        if layer_name in layer.identifier:
            return layer.identifier
    return None
            
def create_hik_character(char_name, bone_map,pr="",create_dummy=False,dummy_root=None):
    cmds.select(clear=True)
    hikNodeNames = []
    for i in range(212):
        hikNodeNames.append(mel.eval(f'GetHIKNodeName({i})'))
    name = mel.eval(f'hikCreateCharacter("{char_name}")')
    dummy_count = 0
    dummy_pos = (0,0,0)
    
        
    for hik_slot, joint_name in bone_map.items():
        hik_id = hikNodeNames.index(hik_slot)
        joints = cmds.listRelatives(pr,ad=True,type="joint",pa=True)
        jdict = dict(zip([s.split("|")[-1] for s in joints],joints))
        
        if not cmds.objExists(joint_name):
            if create_dummy :
                dummy_count += 1
                if not dummy_root == None :
                    if dummy_count == 1 : 
                        cmds.select(dummy_root)
                    dummy_pos = cmds.xform(dummy_root,q=True,t=True,ws=True)
                cmds.joint(p=(dummy_pos[0],dummy_pos[1]+20*dummy_count,dummy_pos[2]), n=joint_name)
            else :
                cmds.warning(f"Joint {joint_name} does not exist, skipping {hik_slot}")
                continue
        if joint_name in jdict:
            joint_name = jdict[joint_name]
            cmds.lockNode(joint_name,l=False)
        mel.eval(f'hikSetCharacterObject("{joint_name}", "{name}", "{hik_id}", 0)')
    return name


def getJointByNameAndParent(name,par):
    joints = cmds.listRelatives(par,ad=True,type="joint",pa=True)
    jd = dict(zip([s.split("|")[-1] for s in joints],joints))
    return jd.get(name,None)
    
def copyJointXForms(source,target):
    print("COPY")
    joints = cmds.listRelatives(source,ad=True,type="joint",pa=True)
    source_dict = dict(zip([s.split("|")[-1] for s in joints],joints))
    joints = cmds.listRelatives(target,ad=True,type="joint",pa=True)
    target_dict = dict(zip([s.split("|")[-1] for s in joints],joints))
    copyXFormFromDictionaries([source_dict,target_dict])
    
def copyJointXFormsFromSelction():
    sl = cmds.ls(sl=True,type="joint")
    jh = []
    for i in range(len(sl)) :
        joints = [sl[i]] + cmds.listRelatives(sl[i],ad=True,type="joint",pa=True)
        jh.append(dict(zip([s.split("|")[-1] for s in joints],joints)))
    copyXFormFromDictionaries(jh)
    
def copyXFormFromDictionaries(dict_list):
    for i in range(1,len(dict_list)):
        for key, value in dict_list[0].items():
            if key in dict_list[i] :
                print(f"COPY {value} to {dict_list[i][key]}")
                local = cmds.xform(value,q=True,m=True)
                target = cmds.xform(dict_list[i][key],q=True,m=True)
                cmds.xform(dict_list[i][key],m=local)

def constrainJoints(source,target):

    joints = cmds.listRelatives(source,ad=True,type="joint",pa=True)
    source_dict = dict(zip([s.split("|")[-1] for s in joints],joints))
    joints = cmds.listRelatives(target,ad=True,type="joint",pa=True)
    target_dict = dict(zip([s.split("|")[-1] for s in joints],joints))
    
    for k,s in source_dict.items() :
        if k in target_dict :
            t = target_dict[k]
            print(f"Parent Constraint {s} to {t}")
            cmds.parentConstraint(t,s,mo=True)

def proxyToRenderAnimTransfer():
    
    
    # Main Steps this script does is 
    #
    #    1 - converts USD data into Maya Data
    #    2 - creates HIK Character Definitions for proxy and render
    #        Some massaging is done do get it to work (creation of dummy nodes, some hardcoded rotation on joints in tpose)
    #    3 - converts USD Render Purpose into Editable Maya Data (Not a duplicate. This is for exporting purposes)
    #    4 - Parent Constraints all joints from the duplicated Render Purposes to the editable Render Purpose
    #        MKaya USD doesnt like when we add attributes to a node since it breaks the USD definition. Its trying to keep a 1 to 1 mapping between USD data and Editable Maya Data. 
    #        HIK needs to add attributes so we make Maya duplicates so we can do what we want and then just parent the transform back on the editable one
    #    5 - Custom expression on the antennas for retargetting so it works as intended. Lots of hardcoded values based of the difference between the two model
    #
    # Manual Steps after the script has run
    #
    #    0 - Unfortunately script doesnt lock the HIK Char Defintion for some reason so lock by hand
    #    1 - Modify animation if needed by adding animation layers to the render purpose duplicate    
    #    2 - Bake Keys of Editble USD Maya Data
    #    3 - Merge back the changes to USD. Open the option box and chose only animation as we are only interested to store the XForms of the USD Skel
    #
    #    Please check recording to show how its done
    
      
    # Define Scene Variables
    stage = "|index|indexShape"
    usd_path_proxy = "/main/proxy/geo"
    usd_path_render = "/main/render/geo"
    animation_proxy_layer = getLayerByName("animated_proxy")
    bone_map_path = os.path.join(os.path.dirname(__file__),"anim_transfer_bones_map.json")
    
    print(bone_map_path)
    # Load Bone Map
    with open(bone_map_path) as f:
        bone_map = json.load(f)
        
    #Get Proxy Purpose USD into Maya Data
    proxy_purpose = mayaUsd.lib.PrimUpdaterManager.duplicate(f"{stage},{usd_path_proxy}", '', {'upAxis': False})
    proxy_purpose = cmds.rename(proxy_purpose,"proxy_purpose")
    
    #Create a Tpose Maya Data Copy of USD by muting anim layer and copying the USD data back into maya again
    cmds.mayaUsdLayerEditor(animation_proxy_layer,e=True,mt=(1,"indexShape")) #mute anim layer
    proxy_tpose = mayaUsd.lib.PrimUpdaterManager.duplicate(f"{stage},{usd_path_proxy}", '', {'upAxis': False})
    proxy_tpose = cmds.rename(proxy_tpose,"proxy_tpose")
    cmds.mayaUsdLayerEditor(animation_proxy_layer,e=True,mt=(0,"indexShape")) #unmute anim layer
    
    #Get Render Purpose USD into Maya Data
    render_purpose = mayaUsd.lib.PrimUpdaterManager.duplicate(f"{stage},{usd_path_render}", '', {'upAxis': False})
    render_purpose = cmds.rename(render_purpose,"render_purpose")
    
    #Custom Hack to align render purpose TPOSE rotation for HIK to lock characters
    rsh = getJointByNameAndParent("R_ShoulderSpin",render_purpose)
    lsh = getJointByNameAndParent("L_ShoulderSpin",render_purpose)
    cmds.rotate(5,0,0,rsh,r=True)
    cmds.rotate(-5,0,0,lsh,r=True)
    
    #copy tpose joints rotation to animation purpose to create a temporary TPOSE for HIK Char Definition Creation
    copyJointXForms(proxy_tpose,proxy_purpose)
    
    #create HIK Character Definitions
    proxy_root_joint = getJointByNameAndParent("Root",proxy_purpose)
    render_root_joint = getJointByNameAndParent("Root",render_purpose)
    proxy_cd = create_hik_character("Odie_Proxy", bone_map['proxy'],pr=proxy_purpose,create_dummy=True,dummy_root=proxy_root_joint)
    render_cd = create_hik_character("Odie_Render", bone_map['render'],pr=render_purpose,create_dummy=True,dummy_root=render_root_joint)

    #Lock HIK Characters - Not Working
    '''
    mel.eval(f'hikCharacterLock("{proxy_cd}", 1, 1 )');
    mel.eval(f'hikCharacterLock("{render_cd}", 1, 1 )');
    

    allSourceChar = cmds.optionMenuGrp("hikSourceList", query=True, itemListLong=True)

    for i,item in enumerate(allSourceChar):
        optMenu = "hikSourceList|OptionMenu"
        sourceChar = cmds.menuItem(item, query=True, label=True)
        if sourceChar == f" {proxy_cd}":
            cmds.optionMenu(optMenu, edit=True, select=i)
            mel.eval('hikUpdateCurrentSourceFromUI()')
            mel.eval('hikUpdateContextualUI()')
            mel.eval('hikControlRigSelectionChangedCallback')
            break
    '''
    # Antenna Parenting
    antenna_L_proxy_name = getJointByNameAndParent("Antenna1_L",proxy_purpose)
    antenna_R_proxy_name = getJointByNameAndParent("Antenna1_R",proxy_purpose)
    antenna_L_render_name = getJointByNameAndParent("L_Antenna_1",render_purpose)
    antenna_R_render_name = getJointByNameAndParent("R_Antenna_1",render_purpose)
    antenna_L_proxy_offset_translation = cmds.getAttr(f"{antenna_L_proxy_name}.translate")[0]
    antenna_R_proxy_offset_translation = cmds.getAttr(f"{antenna_R_proxy_name}.translate")[0]
    antenna_L_proxy_offset_rotation = cmds.getAttr(f"{antenna_L_proxy_name}.rotate")[0]
    antenna_R_proxy_offset_rotation = cmds.getAttr(f"{antenna_R_proxy_name}.rotate")[0]
    antenna_L_render_offset_translation = cmds.getAttr(f"{antenna_L_render_name}.translate")[0]
    antenna_R_render_offset_translation = cmds.getAttr(f"{antenna_R_render_name}.translate")[0]
    antenna_L_render_offset_rotation = cmds.getAttr(f"{antenna_L_render_name}.rotate")[0]
    antenna_R_render_offset_rotation = cmds.getAttr(f"{antenna_R_render_name}.rotate")[0]
    
    antenna_L_mult = (4,-.9,-1.3)
    antenna_R_mult = (4,.9,1.15)
    
    antenna_L_length = 3.69
    antenna_R_length = 3.873
    
    expr = (f"float $diffXL = {antenna_L_proxy_offset_translation[0]} - {antenna_L_proxy_name}.translateX;\n"
            f"float $diffYL = {antenna_L_proxy_offset_translation[1]} - {antenna_L_proxy_name}.translateY;\n"
            f"float $diffZL = {antenna_L_proxy_offset_translation[2]} - {antenna_L_proxy_name}.translateZ;\n"
            f"float $diffXR = {antenna_R_proxy_offset_translation[0]} - {antenna_R_proxy_name}.translateX;\n"
            f"float $diffYR = {antenna_R_proxy_offset_translation[1]} - {antenna_R_proxy_name}.translateY;\n"
            f"float $diffZR = {antenna_R_proxy_offset_translation[2]} - {antenna_R_proxy_name}.translateZ;\n"
            f"{antenna_L_render_name}.translateX = {antenna_L_render_offset_translation[0]} + $diffYL - {antenna_L_mult[0]} * $diffYL / {antenna_L_length};\n"
            f"{antenna_L_render_name}.translateY = {antenna_L_render_offset_translation[1]} + $diffXL * {antenna_L_mult[1]};\n"
            f"{antenna_L_render_name}.translateZ = {antenna_L_render_offset_translation[2]} + $diffZL * {antenna_L_mult[2]};\n"
            f"{antenna_R_render_name}.translateX = {antenna_R_render_offset_translation[0]} - $diffYR + {antenna_R_mult[0]} * $diffYR / {antenna_R_length};\n"
            f"{antenna_R_render_name}.translateY = {antenna_R_render_offset_translation[1]} - $diffXR * {antenna_R_mult[1]};\n"
            f"{antenna_R_render_name}.translateZ = {antenna_R_render_offset_translation[2]} - $diffZR * {antenna_R_mult[2]};\n"
            f"float $rot_offsetXL = {antenna_L_proxy_name}.rotateX - {antenna_L_proxy_offset_rotation[0]};\n"
            f"float $rot_offsetYL = {antenna_L_proxy_name}.rotateY - {antenna_L_proxy_offset_rotation[1]};\n"
            f"float $rot_offsetZL = {antenna_L_proxy_name}.rotateZ - {antenna_L_proxy_offset_rotation[2]};\n"
            f"float $rot_offsetXR = {antenna_R_proxy_name}.rotateX - {antenna_R_proxy_offset_rotation[0]};\n"
            f"float $rot_offsetYR = {antenna_R_proxy_name}.rotateY - {antenna_R_proxy_offset_rotation[1]};\n"
            f"float $rot_offsetZR = {antenna_R_proxy_name}.rotateZ - {antenna_R_proxy_offset_rotation[2]};\n"
            f"{antenna_L_render_name}.rotateX =  {antenna_L_render_offset_rotation[0]} - $rot_offsetYL;\n"
            f"{antenna_L_render_name}.rotateY =  {antenna_L_render_offset_rotation[1]} - $rot_offsetXL;\n"
            f"{antenna_L_render_name}.rotateZ =  {antenna_L_render_offset_rotation[2]} - $rot_offsetZL;\n"
            f"{antenna_R_render_name}.rotateX =  {antenna_R_render_offset_rotation[0]} - $rot_offsetYR;\n"
            f"{antenna_R_render_name}.rotateY =  {antenna_R_render_offset_rotation[1]} - $rot_offsetXR;\n"
            f"{antenna_R_render_name}.rotateZ =  {antenna_R_render_offset_rotation[2]} - $rot_offsetZR;")
  
    cmds.expression(n="Antenna_Expr",s=expr,ae=1,uc="all");
    #print(f"{stage},{usd_path_render}")
    
    
    # Make Render Purpose editable as Maya Data and Constrain the Duplicated Render Purposes maya data driven by HIK to the Editable Render Purpose
    mayaUsd.lib.PrimUpdaterManager.editAsMaya(f"{stage},{usd_path_render}")
    constrainJoints("geoParent|geo",render_purpose)

if __name__ == "__main__":
    proxyToRenderAnimTransfer()
    

    
