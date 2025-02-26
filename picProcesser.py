# -*- coding: utf-8 -*-
from paramsExtract.paramsExtracter import paramExtract
import numpy as np
import cv2
from skimage import morphology
from sklearn.cluster import MeanShift
from operater import operater
import time
from PIL import Image
import matplotlib.pyplot as plt
import tensorflow as tf
from reviewAndTrain.dataStore import dataStore





class picProcesser():
	def __init__(self,test = False):
		self.operater = operater(test=test)
		self.ai = smartAI()
		self.ds = dataStore()
		self.dataInit()

	def dataInit(self):
		'''
		init the data which is need in the processer
		:return:None
		'''
		self.currentPic = None
		#x0,y0,x1,y1
		self.postionData = {
			'HP':[454,686,730,697],
			'MP':[454,699,730,710],
			'MONEY':[798,696,860,712],
			'MAP':[1100,538,1279,719]
		}

		#节点名称介绍
		'''
		首位 L左下边 R右上边
		次位 Base基地（结束） T上 M中 B下
		再次 Node 召唤节点（结束） T塔 R河道边
		再次 1高地塔（结束） 2二塔（结束） 3边塔（结束） 0门牙塔
		再次 0左门牙塔（结束） 1右门牙塔（结束）
'''
		self.nodesPostions = {
			'LSpring':[1105,707],
			'LBase':[1119,694],
			'LBNode':[1142, 699],
			'LBT1':[1151, 700],
			'LBT2':[1182, 697],
			'LBT3':[1223, 700],
			'LBR':[1243,692],
			'RBR':[1254,680],
			'RBT3':[1262, 633],
			'RBT2':[1256, 619],
			'RBT1':[1260, 592],
			'RBNode':[1259, 583],
			'RT01':[1253, 568],
			'RT00':[1247, 563],
			'RBase':[1255, 560],
		}
		self.bottomNodeKeys = ['LSpring','LBase', 'LBNode', 'LBT1', 'LBT2', 'LBT3','LBR','RBR', 'RBT3', 'RBT2', 'RBT1', 'RBNode', 'RT01', 'RT00', 'RBase']
		#数据处理
		self.bottimMiddlePoint = []
		point = np.array([0,0])
		for key in self.bottomNodeKeys:
			newPoint = np.array(self.nodesPostions[key])
			if (point == 0).all():
				point = newPoint
			else:
				middlePoint = 0.5 * (point + newPoint)
				point = newPoint
				self.bottimMiddlePoint.append(middlePoint)

		#创建节点列表
		self.bottomNodeList = []
		for key in self.bottomNodeKeys:
			self.bottomNodeList.append(self.nodesPostions[key])

		#节点插值
		assert len(self.bottomNodeList) != 0
		self.newBottomNodeList = []
		for node in self.bottomNodeList:
			node = np.array(node)
			if len(self.newBottomNodeList) == 0:
				self.newBottomNodeList.append(node)
				continue
			middlePoint = (self.newBottomNodeList[-1] + node) * 0.5
			self.newBottomNodeList.append(middlePoint)
			self.newBottomNodeList.append(node)
		self.bottomNodeList = self.newBottomNodeList.copy()
		assert (len(self.bottomNodeList) != 0)
		#HP提取时用的中间的斜线
		self.HPxieImg = cv2.imread('resource/xie.png')
		self.HPxieImg = cv2.cvtColor(self.HPxieImg, cv2.COLOR_BGR2GRAY)

	def findPic(self,oriImg, targetImg, threshold=0.8, delay=0.5, test=False):
		point = [0, 0]
		h, w = targetImg.shape[:2]  # rows->h, cols->w
		res = cv2.matchTemplate(oriImg, targetImg, cv2.TM_CCOEFF_NORMED)
		min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
		maxValue = np.max(res)

		if maxValue > threshold or True:
			left_top = max_loc  # 左上角
			right_bottom = (left_top[0] + w, left_top[1] + h)  # 右下角
			if test:

				img = oriImg.copy()
				cv2.rectangle(img, left_top, right_bottom, 255, 1)  # 画出矩形位置
				cv2.imwrite('result.png', img)

			return [left_top, right_bottom]


	def elementExtract(self,elementName,oriPic):
		'''
		从图片中提取某些元素，如小地图，血条，蓝条等，具体数据在self.postionData
		:param elementName: 元素名称 具体看那个字典
		:param oriPic: 原始图片 格式cv2图片
		:return: 返回地图，格式cv2图片
		'''

		print ('elementExtract elment:{}'.format(elementName))
		targetArea = self.postionData.get(elementName,None)
		assert targetArea is not None
		pic = oriPic[targetArea[1]:targetArea[3], targetArea[0]:targetArea[2]]
		print(pic.shape)
		return pic

	def loadPic(self,path= 'res/Screen01.png'):
		pic=cv2.imread(path)
		return pic

	def picDisplay(self,pic,saveName = '',PIL = False,noDis = False):
		if np.max(pic) <= 1:
			pic = pic * 255
		if not noDis:
			if not PIL:
				cv2.imshow('pic',pic)
				cv2.waitKey(0)
				cv2.destroyAllWindows()
			else:
				plt.figure(saveName)
				plt.imshow(pic)
				plt.show()
		if saveName != '':
			cv2.imwrite('ans/'+saveName+'.png',pic)

	def pointTransform(self,pointIn,map2all = False):
		'''
		:param pointIn: 输入坐标，【X，Y】
		:param map2all: 如果是小地图转通用坐标，该参数为True
		:return:返回坐标值列表，【y，x】
		'''
		pointIn = pointIn.copy()
		yOffset = self.postionData['MAP'][0]
		xOffset = self.postionData['MAP'][1]
		addRatio = -1
		if map2all:
			addRatio = 1
		pointIn[0] += addRatio * yOffset
		pointIn[1] += addRatio * xOffset
		return pointIn


	def determineAction(self,params = {}):
		'''
		通过输入图片决定所需动作 局势检测等在此实现
		:param pic: 当前完整图片
		:return: 动作字典
		'''

		pic = self.currentPic

		go = 1
		HPpercent = params.get('HP',-1)
		print('当前HP:{}'.format(HPpercent))
		if HPpercent == -1:
			pass
		elif HPpercent < 0.95:
			print('撤退')
			go = -1

		action = {
			'go':go
		}
		return action

	def actionExcute(self,action,params):
		'''
		执行程序发出的指令到游戏
		:param action:指令字典
		:return:无
		'''
		go = action['go']
		targetPostionName = ''
		if go == 1:
			targetPostionName = 'go'
		elif go == -1:
			targetPostionName = 'back'

		targetPostion = params.get(targetPostionName,None)
		if targetPostion is not None:
			self.operater.MoveToMapPostion(targetPostion,targetPostionName == 'go')

	def getPic(self,pic):
		'''
		获取图片的函数，图片从此开始处理
		:param pic:游戏全图
		:return:
		'''

		assert (pic.shape == (720,1280,3))
		same = (pic == self.currentPic).all()
		print('获取图片 重复判断结果：{}'.format(same))
		if same:
			return
		self.currentPic = pic
		# cv2.imwrite('1.png', pic)
		params = paramExtract(self)
		# cv2.imwrite('2.png', pic)
		action = self.determineAction(params)
		# cv2.imwrite('3.png', pic)
		self.ds.storeResult(pic,params,action)
		# cv2.imwrite('4.png', pic)
		self.actionExcute(action,params)

	def mainLoop(self):
		while(True):
			newT = time.time()
			ret = self.operater.Capture(0, 0, 2000, 2000, r"E:\develop\autoLOL\dm\screen1/0.bmp")
			#print('截图结果：{}'.format(ret))
			if ret == 0:
				print('capture fail')
				time.sleep(1)
			#print('截图完成 花费时间：{}'.format(time.time() - newT))
			pic = self.loadPic(r'E:\develop\autoLOL\dm\screen1/0.bmp')
			#print('读取图片完成 花费时间：{}'.format(time.time() - newT))
			if pic is not None:
				self.getPic(pic)
				print('命令发送完成 花费时间：{}'.format(time.time() - newT))
			else:
				time.sleep(0.1)


class smartAI():
	def __init__(self):
		self.models = {}
		self.HPdigitModel_ = None
		self.HPdigits = []
		x = []
		i = 0
		while True:
			pic = cv2.imread(r'jupyter/shuzi/{}.png'.format(i))
			if pic is None:
				break
			pic = cv2.cvtColor(pic, cv2.COLOR_BGR2GRAY)
			x.append(pic)
			i += 1
		self.x = np.array(x)


	def useModel(self,modelName,inputData):
		'''
		使用模型预测值
		:param modelName: 模型名称
		:param inputData: 输入数据
		:return: 预测数据
		'''
		model = self.models.get(modelName,None)
		if model is None:
			model = self.addModel(modelName)
		print('input',inputData.shape)
		predictions = model.predict(inputData)

		return predictions


	def addModel(self,modelName):
		self.models[modelName] = tf.keras.models.load_model(r'model/{}'.format(modelName))
		return self.models[modelName]


	def HPdigitModel(self):
		if self.HPdigitModel_ is not None:
			return self.HPdigitModel_
		else:
			self.HPdigitModel_ = tf.keras.models.load_model(r'model/HP_Num_Recognition_model.h5')
			return self.HPdigitModel_

	def hpDightRecognizate(self,charImgs):

		for img in charImgs:
			if img.shape == (11,6):
				continue

			plt.figure('')
			plt.imshow(img)
			plt.show()

		
		charImgs = np.uint8(np.array(charImgs))

		print('there are {} imgs to recognize || shape is {}'.format(len(charImgs),charImgs.shape))
		ansLs = []
		for i in range(len(charImgs)):
			targetImg = charImgs[i] * 255

			predictions = self.HPdigitModel().predict(targetImg.reshape(1,11,6))
			ans = np.argmax(predictions)

			ansLs.append(ans)

		return ansLs


if __name__ == "__main__":
	p = picProcesser()
	p.mainLoop()
	exit()



