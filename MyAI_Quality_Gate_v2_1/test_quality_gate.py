import unittest
from quality_gate import rule_flags,money_canonical

def row(q,a):return {'prompt':[{'role':'system','content':'Test'},{'role':'user','content':q}], 'completion':[{'role':'assistant','content':a}]}

class TestQualityGate(unittest.TestCase):
 def test_identity(self):
  h,_=rule_flags(row('Xin chào','Mình là EmpathAI, sẵn sàng hỗ trợ.'))
  self.assertIn('other_chatbot_identity_in_answer',h)
 def test_booking_without_evidence(self):
  h,_=rule_flags(row('Cho mình đặt lịch ngày mai.','Dạ em đã đặt lịch thành công ạ.'))
  self.assertIn('unverified_action_booking',h)
 def test_booking_with_evidence(self):
  h,_=rule_flags(row('Cho mình đặt lịch. KẾT QUẢ HỆ THỐNG: {"status":"confirmed","booking_id":"BK-123"}','Dạ em đã đặt lịch thành công ạ.'))
  self.assertNotIn('unverified_action_booking',h)
 def test_acknowledgement(self):
  h,_=rule_flags(row('Tôi mua hàng hôm qua, giao thiếu.','Dạ mình đã ghi nhận phản ánh về đơn giao thiếu; xin cung cấp mã đơn.'))
  self.assertFalse(h)
 def test_money_normalization(self):
  self.assertEqual(money_canonical('25k'),money_canonical('25.000đ'))
 def test_hallucinated_money_needs_review(self):
  h,m=rule_flags(row('Bánh tráng giá 25.000đ', 'Giá là 30.000đ ạ.'))
  self.assertIn('answer_money_not_evidenced',m)
 def test_grounded_money(self):
  h,m=rule_flags(row('Bánh tráng giá 25.000đ', 'Giá là 25k ạ.'))
  self.assertNotIn('answer_money_not_evidenced',m)

if __name__=='__main__':unittest.main()
