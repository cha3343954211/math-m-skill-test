function [j] = xiayige_hang(cell,num)


for i=1:length(cell)
    level=graythresh(cell{1,i});
    cell{1,i}=imbinarize(cell{1,i},level);  %图像二值化处理
end

lis = zeros(length(cell),1);
for i = 1:length(cell)
    if i == num
        tt = 0;
    end
    tt = sum( cell{1,num}(:,72) == cell{1,i}(:,1) ) ;
    lis(i) = tt;
    [i,j] = max(lis);
    
    
end



end

